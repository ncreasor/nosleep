import os
import uuid
import asyncio
import json
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
import anthropic

from database import get_db
from models import Document, User, AuditLog, Template, DocumentCorrection, Chat, ChatMessage
from schemas import (
    DocumentResponse,
    DocumentUpdate,
    DocumentSearchResult,
    DocumentAnalysis,
    DocumentInsights,
    DocumentCreate,
    DocumentErrors,
    GenerateTemplateRequest,
    TemplateResponse,
    DocumentCorrectionCreate,
    DocumentCorrectionResponse,
    UserStatisticsSummary,
    AnalysisStatistics,
    DocumentSnapshotsPut,
    DocumentSnapshotsGet,
    DocumentAiChatMessagePost,
    DocumentAiChatMessageIdBody,
    DocumentAiChatStateResponse,
    DocumentAiChatApproveResponse,
    DocumentAiChatOkResponse,
    AiChatMessageItem,
    AiChatProposedEdit,
)
from auth import get_current_user
from config import settings
from processing import (
    background_process_document,
    get_qdrant_client,
    ensure_collection,
    extract_entities_from_document,
    extract_relations_from_document,
    parse_document_structure,
    extract_definitions,
)
from forensics import DocumentForensics, format_forensic_report
from llm_json import parse_llm_json
from document_protection import document_to_response, is_reference_contract_protected
from template_render import pack_template_content
from document_ai_chat import (
    run_document_ai_chat_turn,
    assistant_message_to_json,
    parse_stored_assistant_message,
    merge_message_status,
)

router = APIRouter(prefix="/documents", tags=["documents"])
UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}


async def _document_for_user(
    db: AsyncSession, document_id: int, current_user: User
) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.user_id is not None and doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к документу"
        )
    return doc


async def _get_or_create_doc_ai_chat(
    db: AsyncSession, user_id: int, document_id: int, doc_title: str
) -> Chat:
    r = await db.execute(
        select(Chat).where(Chat.document_id == document_id, Chat.user_id == user_id)
    )
    chat = r.scalar_one_or_none()
    if chat:
        return chat
    safe_title = (doc_title or "Документ")[:120]
    chat = Chat(
        user_id=user_id,
        document_id=document_id,
        title=f"AI-Chat · {safe_title}",
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat


def _messages_to_ai_chat_items(rows: list) -> list[AiChatMessageItem]:
    items: list[AiChatMessageItem] = []
    for m in rows:
        assistant = parse_stored_assistant_message(m.content) if m.role == "assistant" else None
        items.append(
            AiChatMessageItem(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
                assistant=assistant,
            )
        )
    return items


def _history_pairs_from_messages(rows: list[ChatMessage]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for m in rows:
        if m.role == "user":
            out.append(("user", m.content))
        elif m.role == "assistant":
            parsed = parse_stored_assistant_message(m.content)
            out.append(("assistant", (parsed or {}).get("reply") or m.content))
    return out


def _apply_edits_plain(text: str, edits: list[dict]) -> tuple[str | None, str | None]:
    t = text or ""
    sorted_edits = sorted([e for e in edits if isinstance(e, dict) and e.get("find")], key=lambda x: -len(x["find"]))
    for e in sorted_edits:
        find = e["find"]
        repl = e.get("replace", "")
        if find not in t or t.count(find) != 1:
            return None, f"Фрагмент не найден или встречается несколько раз: «{find[:80]}»"
        t = t.replace(find, repl, 1)
    return t, None


def _parse_saved_json(raw: str | None) -> dict | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def ensure_upload_dir():
    UPLOAD_DIR.mkdir(exist_ok=True)


def check_file_valid(filename: str, size_bytes: int) -> str:
    """Validate file. Returns error msg or empty string if valid."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        return f"File too large. Max {settings.max_file_size_mb} MB"

    return ""


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    folder_id: int | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await ensure_upload_dir()

    content = await file.read()
    error = check_file_valid(file.filename, len(content))
    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    file_id = str(uuid.uuid4())
    file_name = f"{file_id}_{file.filename}"
    file_path = UPLOAD_DIR / file_name

    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        user_id=current_user.id,
        folder_id=folder_id,
        title=file.filename,
        filename=file.filename,
        file_path=str(file_path),
        content_type=file.content_type,
        size=len(content),
        status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    log = AuditLog(
        user_id=current_user.id,
        action="document.upload",
        resource_type="document",
        resource_id=doc.id,
        detail=f"Uploaded {file.filename} ({len(content)} bytes)",
    )
    db.add(log)
    await db.commit()

    asyncio.create_task(background_process_document(doc.id))

    return document_to_response(doc)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    doc_data: DocumentCreate,
    user_id: int = 1,
    db: AsyncSession = Depends(get_db),
):
    """Create a document with text content directly"""
    extracted_text = doc_data.extracted_text or ""
    doc = Document(
        user_id=user_id,
        folder_id=doc_data.folder_id,
        title=doc_data.title,
        filename=doc_data.filename or f"{doc_data.title}.txt",
        file_path=None,
        content_type="text/plain",
        size=len(extracted_text),
        status="completed",
        extracted_text=extracted_text,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    log = AuditLog(
        user_id=user_id,
        action="document.create",
        resource_type="document",
        resource_id=doc.id,
        detail=f"Created {doc_data.title}",
    )
    db.add(log)
    await db.commit()

    return document_to_response(doc)


@router.get("/search", response_model=list[DocumentSearchResult])
async def search_documents(
    q: str,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Query too short")

    try:
        from processing import generate_embedding
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        query_embedding = generate_embedding(q)
        client = get_qdrant_client()
        ensure_collection(client)

        try:
            filter_cond = Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=current_user.id))]
            )
            results = client.search(
                collection_name=settings.qdrant_collection,
                query_vector=query_embedding,
                limit=limit,
                query_filter=filter_cond,
                with_payload=True,
            )

            search_results = []
            for hit in results:
                payload = hit.payload
                search_results.append(
                    DocumentSearchResult(
                        id=payload["doc_id"],
                        title=payload["title"],
                        classification=payload.get("classification"),
                        score=hit.score,
                        snippet=payload.get("snippet", ""),
                    )
                )

            return search_results
        except Exception as qdrant_err:
            return []

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=UserStatisticsSummary)
async def get_user_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_r = await db.execute(
        select(func.count(DocumentCorrection.id)).where(
            DocumentCorrection.user_id == current_user.id
        )
    )
    total = int(total_r.scalar() or 0)

    by_type_r = await db.execute(
        select(DocumentCorrection.error_type, func.count(DocumentCorrection.id))
        .where(DocumentCorrection.user_id == current_user.id)
        .group_by(DocumentCorrection.error_type)
    )
    by_type = {row[0]: int(row[1]) for row in by_type_r.all()}

    # Compute analysis statistics from saved snapshots
    docs_r = await db.execute(
        select(Document.saved_analysis_json).where(
            Document.user_id == current_user.id,
            Document.saved_analysis_json.isnot(None),
        )
    )
    docs_analyzed = 0
    total_norms = 0
    grounded = 0
    ungrounded = 0
    confidence_sum = 0.0
    confidence_count = 0
    by_verdict: dict[str, int] = {}

    for (raw_json,) in docs_r.all():
        parsed = _parse_saved_json(raw_json)
        if not parsed:
            continue
        norms = parsed.get("norms_analysis", {})
        articles = norms.get("articles")
        if not isinstance(articles, list) or not articles:
            continue
        docs_analyzed += 1
        total_norms += len(articles)
        for art in articles:
            g = art.get("grounding")
            if g and isinstance(g, dict):
                verdict = g.get("verdict", "unclear")
                by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
                gc = g.get("grounding_confidence")
                if isinstance(gc, (int, float)):
                    confidence_sum += gc
                    confidence_count += 1
                if verdict in ("applicable", "partially_applicable"):
                    grounded += 1
                else:
                    ungrounded += 1
            else:
                ungrounded += 1

    analysis_stats = AnalysisStatistics(
        documents_analyzed=docs_analyzed,
        total_norms_found=total_norms,
        grounded_norms=grounded,
        ungrounded_norms=ungrounded,
        avg_confidence=round(confidence_sum / confidence_count, 1) if confidence_count else None,
        by_verdict=by_verdict,
    )

    return UserStatisticsSummary(
        corrections_total=total,
        corrections_by_type=by_type,
        analysis=analysis_stats,
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .offset(skip)
        .limit(limit)
    )
    return [document_to_response(d) for d in result.scalars().all()]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document_to_response(doc)


@router.get("/{document_id}/snapshots", response_model=DocumentSnapshotsGet)
async def get_document_snapshots(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Load saved JSON for analysis (entities + norms) and changes (formulation, AI-Chat)."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.user_id is not None and doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к документу")
    return DocumentSnapshotsGet(
        analysis=_parse_saved_json(doc.saved_analysis_json),
        changes=_parse_saved_json(doc.saved_changes_json),
    )


@router.put("/{document_id}/snapshots", response_model=DocumentSnapshotsGet)
async def put_document_snapshots(
    document_id: int,
    body: DocumentSnapshotsPut,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist analysis and/or changes as JSON on the document."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if doc.user_id is not None and doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к документу")

    if body.analysis is not None:
        doc.saved_analysis_json = json.dumps(body.analysis, ensure_ascii=False)
    if body.changes is not None:
        doc.saved_changes_json = json.dumps(body.changes, ensure_ascii=False)
    await db.commit()
    await db.refresh(doc)
    return DocumentSnapshotsGet(
        analysis=_parse_saved_json(doc.saved_analysis_json),
        changes=_parse_saved_json(doc.saved_changes_json),
    )


@router.get("/{document_id}/text")
async def get_document_text(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return {
        "id": doc.id,
        "title": doc.title,
        "text": doc.extracted_text or "",
        "status": doc.status,
    }


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return FileResponse(
        path=doc.file_path,
        media_type=doc.content_type,
        filename=doc.filename,
    )


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    schema: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await _document_for_user(db, document_id, current_user)
    if schema.title is not None:
        doc.title = schema.title
    if schema.extracted_text is not None:
        doc.extracted_text = schema.extracted_text
    await db.commit()
    await db.refresh(doc)
    return document_to_response(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.user_id is not None and doc.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к документу")

    if is_reference_contract_protected(doc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Этот демонстрационный договор нельзя удалить",
        )

    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.execute(delete(Document).where(Document.id == document_id))

    log = AuditLog(
        user_id=current_user.id,
        action="document.delete",
        resource_type="document",
        resource_id=document_id,
        detail=f"Deleted {doc.title}",
    )
    db.add(log)
    await db.commit()


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    asyncio.create_task(background_process_document(document_id))
    return document_to_response(doc)


@router.get("/{document_id}/analysis", response_model=DocumentAnalysis)
async def analyze_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed analysis of document: entities, relations, structure, definitions."""
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not doc.extracted_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document not yet processed")

    entities = extract_entities_from_document(doc.extracted_text)
    relations = extract_relations_from_document(doc.extracted_text)
    structure = parse_document_structure(doc.extracted_text)
    definitions = extract_definitions(doc.extracted_text)

    return DocumentAnalysis(
        entities=entities,
        relations=relations,
        structure=structure,
        definitions=definitions,
    )


@router.get("/{document_id}/insights", response_model=DocumentInsights)
async def get_document_insights(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get high-level insights about document."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not doc.extracted_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document not yet processed")

    entities_data = extract_entities_from_document(doc.extracted_text)
    relations_data = extract_relations_from_document(doc.extracted_text)
    structure_data = parse_document_structure(doc.extracted_text)
    definitions_data = extract_definitions(doc.extracted_text)

    # Extract key terms from definitions
    key_terms = list(definitions_data.get("definitions", {}).keys())[:10]

    return DocumentInsights(
        document_id=doc.id,
        title=doc.title,
        classification=doc.classification,
        entities_count=entities_data.get("total", 0),
        relations_count=relations_data.get("total", 0),
        sections_count=structure_data.get("sections_count", 0),
        definitions_count=definitions_data.get("total", 0),
        key_terms=key_terms,
    )


@router.get("/{document_id}/forensics")
async def forensic_analysis(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyze document for forgery indicators and authenticity."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not doc.extracted_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document not yet processed")

    # Run forensic analysis
    forensic_report = DocumentForensics.analyze(doc.extracted_text, doc.file_path)

    return format_forensic_report(forensic_report)


@router.get("/{document_id}/errors", response_model=DocumentErrors)
async def get_document_errors(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Analyze document for legal errors — grounded in local DB + Qdrant RAG.
    First extracts norm references, validates each against the law database,
    then asks Claude to analyze ONLY with retrieved evidence."""
    import re
    import logging as _logging
    from laws_validator import validate_norm, parse_norm_reference
    from laws_rag import LawsRAG

    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not doc.extracted_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document not yet processed")

    doc_text = doc.extracted_text[:8000]

    # Step 1: Extract all norm references from document text
    norm_pattern = re.compile(
        r'(?:статьей|статьями|стать[яиею]|ст\.?)\s+(\d+(?:\s*,\s*\d+)*)\s+'
        r'(Трудового кодекса(?:\s+Республики\s+Казахстан)?|ТК\s+РК'
        r'|Гражданского кодекса(?:\s+(?:Республики\s+Казахстан|РК))?|ГК\s+РК'
        r'|Уголовного кодекса(?:\s+РК)?|УК\s+РК'
        r'|Налогового кодекса(?:\s+РК)?|НК\s+РК'
        r'|Гражданского процессуального кодекса(?:\s+РК)?|ГПК\s+РК'
        r'|Уголовно-процессуального кодекса(?:\s+РК)?|УПК\s+РК'
        r'|КоАП\s+РК|ЖК\s+РК|СК\s+РК|ЗК\s+РК'
        r'|Земельного кодекса(?:\s+РК)?'
        r'|Закона\s+РК[^"]{0,60})',
        re.IGNORECASE,
    )
    found_norms: list[dict] = []
    for m in norm_pattern.finditer(doc_text):
        articles_str = m.group(1)
        law_part = m.group(2).strip()
        for art_num in re.split(r'\s*,\s*', articles_str):
            ref_text = f"ст. {art_num.strip()} {law_part}"
            validation = validate_norm(ref_text)
            found_norms.append({
                "reference": ref_text,
                "original_match": m.group(0),
                "validation": validation,
            })

    # Step 2: Build grounding context from DB validation results
    db_grounding_lines: list[str] = []
    for fn in found_norms:
        v = fn["validation"]
        if v.get("valid"):
            db_grounding_lines.append(
                f'✓ {fn["reference"]}: найдена в базе — "{v.get("title", "")}", статус: {v.get("status", "unknown")}'
            )
        else:
            db_grounding_lines.append(
                f'✗ {fn["reference"]}: НЕ найдена — {v.get("reason", "неизвестная причина")}'
            )

    db_grounding = "\n".join(db_grounding_lines) if db_grounding_lines else "Ссылки на нормы не обнаружены в тексте."

    # Step 3: RAG search for broader context (formulation issues etc.)
    rag = LawsRAG()
    rag_context = ""
    try:
        # Search for the document's general legal domain
        first_500 = doc_text[:500]
        rag_results = await rag.search(query=first_500, language="rus", top_k=3, use_reranking=False)
        for r in rag_results:
            rag_context += f"--- {r['title']} ({r.get('number', '')}) ---\n"
            rag_context += f"Статус: {'действует' if r.get('is_active') else 'утратил силу'}\n"
            rag_context += f"{r['text'][:400]}\n\n"
    except Exception as rag_err:
        _logging.warning("RAG search for errors context failed: %s", rag_err)

    # Step 4: Ask Claude to analyze with grounding evidence only
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    prompt = f"""Проанализируй казахстанский юридический документ на ошибки. Используй ТОЛЬКО предоставленные ниже факты для обоснования.

РЕЗУЛЬТАТЫ ПРОВЕРКИ ССЫЛОК НА НОРМЫ ПО БАЗЕ ДАННЫХ:
{db_grounding}

ФРАГМЕНТЫ ИЗ БАЗЫ ЗАКОНОДАТЕЛЬСТВА (для контекста):
{rag_context if rag_context else "Нет дополнительного контекста."}

ТЕКСТ ДОКУМЕНТА:
{doc_text}

ПРАВИЛА:
1. Тип "law_ref": указывай ТОЛЬКО если ссылка помечена ✗ (не найдена в базе) выше. НЕ выдумывай несуществующие ошибки.
2. Тип "outdated": указывай ТОЛЬКО если статус нормы в базе — не "valid", или если во фрагментах из базы явно указано, что норма утратила силу.
3. Тип "formulation": указывай только явные грамматические или терминологические ошибки в тексте документа, подтверждаемые фрагментами из базы.
4. Если всё в порядке и ошибок нет — верни пустой список errors.
5. НЕ выдумывай поправки, замены или несуществующие статьи.
6. Поле "original_text" — точная подстрока из текста документа.

Верни ТОЛЬКО JSON:
{{
  "summary": "краткое резюме 2-3 предложения",
  "errors": [
    {{"id": "e1", "type": "law_ref", "title": "...", "original_text": "...", "suggestion": "...", "reason": "...", "grounded": true}}
  ]
}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": prompt}],
            system="Ты эксперт по праву РК. Анализируешь документы ТОЛЬКО на основании предоставленных фактов из базы данных. Не придумывай ошибки. Отвечай только валидным JSON.",
            temperature=0.1,
            max_tokens=2000,
        )

        content = response.content[0].text.strip()

        try:
            data = parse_llm_json(content)

            # Post-validate: ensure law_ref errors are actually grounded in DB results
            validated_errors = []
            invalid_refs = {fn["reference"] for fn in found_norms if not fn["validation"].get("valid")}
            for i, e in enumerate(data.get("errors", [])):
                error_entry = {
                    "id": e.get("id", f"e{i}"),
                    "type": e.get("type", "formulation"),
                    "title": e.get("title", "Ошибка"),
                    "original_text": e.get("original_text", ""),
                    "suggestion": e.get("suggestion", ""),
                    "reason": e.get("reason", ""),
                }
                # For law_ref errors, verify the claim is actually backed by DB
                if error_entry["type"] == "law_ref":
                    orig = error_entry["original_text"]
                    is_grounded = any(ref in orig or orig in ref for ref in invalid_refs)
                    if not is_grounded:
                        # LLM hallucinated this error — skip it
                        continue
                # Verify original_text exists in document
                if error_entry["original_text"] and error_entry["original_text"] not in doc_text:
                    continue
                validated_errors.append(error_entry)

            return DocumentErrors(
                summary=data.get("summary", ""),
                errors=validated_errors,
            )
        except json.JSONDecodeError:
            return DocumentErrors(
                summary="Не удалось проанализировать документ",
                errors=[]
            )

    except Exception as e:
        _logging.error(f"Error analyzing document for errors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{document_id}/corrections",
    response_model=DocumentCorrectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_document_correction(
    document_id: int,
    body: DocumentCorrectionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _document_for_user(db, document_id, current_user)

    et = (body.error_type or "formulation").strip()[:32]
    row = DocumentCorrection(
        document_id=document_id,
        user_id=current_user.id,
        error_id=(body.error_id[:64] if body.error_id else None),
        error_type=et,
        title=(body.title[:512] if body.title else None),
        original_text=body.original_text,
        suggestion=body.suggestion,
        reason=body.reason,
    )
    db.add(row)
    log = AuditLog(
        user_id=current_user.id,
        action="document.correction",
        resource_type="document",
        resource_id=document_id,
        detail=f"type={et}",
    )
    db.add(log)
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/{document_id}/corrections", response_model=list[DocumentCorrectionResponse])
async def list_document_corrections(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _document_for_user(db, document_id, current_user)

    r = await db.execute(
        select(DocumentCorrection)
        .where(DocumentCorrection.document_id == document_id)
        .order_by(DocumentCorrection.created_at.desc())
    )
    return r.scalars().all()


@router.get("/{document_id}/ai-chat", response_model=DocumentAiChatStateResponse)
async def get_document_ai_chat(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await _document_for_user(db, document_id, current_user)
    chat = await _get_or_create_doc_ai_chat(db, current_user.id, document_id, doc.title or "")
    r = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.chat_id == chat.id)
        .order_by(ChatMessage.created_at)
    )
    rows = list(r.scalars().all())
    return DocumentAiChatStateResponse(
        chat_id=chat.id, messages=_messages_to_ai_chat_items(rows)
    )


@router.post("/{document_id}/ai-chat/message", response_model=DocumentAiChatStateResponse)
async def post_document_ai_chat_message(
    document_id: int,
    body: DocumentAiChatMessagePost,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    text = (body.message or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пустое сообщение")

    doc = await _document_for_user(db, document_id, current_user)
    chat = await _get_or_create_doc_ai_chat(db, current_user.id, document_id, doc.title or "")

    user_row = ChatMessage(chat_id=chat.id, role="user", content=text)
    db.add(user_row)
    await db.commit()
    await db.refresh(user_row)

    r = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.chat_id == chat.id)
        .order_by(ChatMessage.created_at)
    )
    all_msgs = list(r.scalars().all())
    history = _history_pairs_from_messages(all_msgs[:-1])
    doc_text = (
        body.document_plain_text
        if body.document_plain_text is not None
        else (doc.extracted_text or "")
    )

    try:
        payload = run_document_ai_chat_turn(
            document_text=doc_text,
            history=history,
            user_message=text,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    assistant_json = assistant_message_to_json(payload)
    asst_row = ChatMessage(chat_id=chat.id, role="assistant", content=assistant_json)
    db.add(asst_row)
    log = AuditLog(
        user_id=current_user.id,
        action="document.ai_chat",
        resource_type="document",
        resource_id=document_id,
        detail="assistant_reply",
    )
    db.add(log)
    await db.commit()
    await db.refresh(asst_row)

    r2 = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.chat_id == chat.id)
        .order_by(ChatMessage.created_at)
    )
    rows = list(r2.scalars().all())
    return DocumentAiChatStateResponse(
        chat_id=chat.id, messages=_messages_to_ai_chat_items(rows)
    )


@router.post("/{document_id}/ai-chat/approve", response_model=DocumentAiChatApproveResponse)
async def approve_document_ai_chat(
    document_id: int,
    body: DocumentAiChatMessageIdBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await _document_for_user(db, document_id, current_user)
    r = await db.execute(
        select(Chat).where(
            Chat.document_id == document_id, Chat.user_id == current_user.id
        )
    )
    chat = r.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чат не найден")

    msg = await db.get(ChatMessage, body.message_id)
    if not msg or msg.chat_id != chat.id or msg.role != "assistant":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сообщение не найдено")

    parsed = parse_stored_assistant_message(msg.content)
    if not parsed or parsed.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет правок на согласование",
        )

    edits_raw = parsed.get("proposed_edits") or []
    if not edits_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет предложенных замен",
        )

    base = (
        body.document_plain_text
        if body.document_plain_text is not None
        else (doc.extracted_text or "")
    )
    merged, err = _apply_edits_plain(base, edits_raw)
    if err or merged is None:
        return DocumentAiChatApproveResponse(
            ok=False,
            edits=[],
            merged_plain=None,
            detail=err or "Не удалось применить замены",
        )

    msg.content = merge_message_status(msg.content, "applied") or msg.content
    doc.extracted_text = merged

    for e in edits_raw:
        if not isinstance(e, dict) or not e.get("find"):
            continue
        db.add(
            DocumentCorrection(
                document_id=document_id,
                user_id=current_user.id,
                error_id=None,
                error_type="ai_chat",
                title="AI-Chat",
                original_text=e["find"],
                suggestion=str(e.get("replace", "")),
                reason=e.get("reason"),
            )
        )
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="document.ai_chat_approve",
            resource_type="document",
            resource_id=document_id,
            detail=f"message_id={body.message_id}",
        )
    )
    await db.commit()

    out_edits: list[AiChatProposedEdit] = []
    for e in edits_raw:
        if not isinstance(e, dict):
            continue
        out_edits.append(
            AiChatProposedEdit(
                find=e.get("find", ""),
                replace=str(e.get("replace", "")),
                reason=e.get("reason"),
            )
        )
    return DocumentAiChatApproveResponse(
        ok=True, edits=out_edits, merged_plain=merged, detail=None
    )


@router.post("/{document_id}/ai-chat/reject", response_model=DocumentAiChatOkResponse)
async def reject_document_ai_chat(
    document_id: int,
    body: DocumentAiChatMessageIdBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _document_for_user(db, document_id, current_user)
    r = await db.execute(
        select(Chat).where(
            Chat.document_id == document_id, Chat.user_id == current_user.id
        )
    )
    chat = r.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чат не найден")

    msg = await db.get(ChatMessage, body.message_id)
    if not msg or msg.chat_id != chat.id or msg.role != "assistant":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сообщение не найдено")

    parsed = parse_stored_assistant_message(msg.content)
    if not parsed or parsed.get("status") != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет правок на отклонение",
        )

    msg.content = merge_message_status(msg.content, "rejected") or msg.content
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="document.ai_chat_reject",
            resource_type="document",
            resource_id=document_id,
            detail=f"message_id={body.message_id}",
        )
    )
    await db.commit()
    return DocumentAiChatOkResponse(ok=True)


@router.post("/{document_id}/generate-template", response_model=TemplateResponse)
async def generate_template_from_document(
    document_id: int,
    request: GenerateTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a template from a document by analyzing its structure and variables.
    The template can be edited and used to generate similar documents.
    """
    try:
        doc = await _document_for_user(db, document_id, current_user)

        if not doc.extracted_text:
            raise HTTPException(status_code=400, detail="Document text not extracted yet")

        template_content = await _generate_template_content(doc.extracted_text)
        packed = pack_template_content(template_content)

        # Create template in database
        template = Template(
            user_id=current_user.id,
            folder_id=request.folder_id,
            source_document_id=document_id,
            name=request.name or f"Шаблон: {doc.title}",
            description=f"Сгенерировано из документа: {doc.title}",
            content=json.dumps(packed, ensure_ascii=False, indent=2),
            tags=template_content.get("document_type", ""),
        )

        db.add(template)
        await db.commit()
        await db.refresh(template)

        # Log action
        audit_log = AuditLog(
            user_id=current_user.id,
            action="create_template_from_document",
            resource_type="template",
            resource_id=template.id,
            detail=f"Created from document {document_id}",
        )
        db.add(audit_log)
        await db.commit()

        return template

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error generating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_template_content(text: str) -> dict:
    """
    Use Claude to analyze document and extract template structure with variables.
    Returns JSON with sections and variables.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Truncate text to avoid excessive tokens
    truncated_text = text[:6000]

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            messages=[
                {
                    "role": "user",
                    "content": f"""Create a template from this document following the system rules:
- Redact dates and natural persons' names into {{{{snake_case_ids}}}}
- Keep company/organization names and legal structure

DOCUMENT:
---
{truncated_text}
---

Return JSON format:
{{
  "document_type": "Тип документа на русском",
  "sections": [
    {{
      "id": "section-id",
      "title": "Section Title",
      "order": 1,
      "content": "Section text with {{{{placeholder_id}}}} and more text",
      "variables": [
        {{
          "id": "placeholder_id",
          "label": "Human-readable label in Russian",
          "type": "text",
          "default": "",
          "placeholder": "Example value"
        }}
      ]
    }}
  ]
}}

CRITICAL: Return ONLY JSON, no other text.""",
                },
            ],
            system="""You are a legal document template generator for Kazakhstan/Russian contracts.

GOAL: Turn this ONE concrete document into a reusable template.

MUST PRESERVE (keep exact wording in "content"):
- Company / legal entity names: ТОО, АО, ИП, LLP, names in quotes after them, «…», юридический адрес организации
- Statutory references, article numbers, law names (ТК РК, ГК РК, etc.)
- General legal boilerplate clauses that are not person-specific

MUST REPLACE with {{placeholder_id}} (snake_case Latin IDs):
- All calendar dates and phrases like «16 апреля 2026 г.», «10.03.2020», years alone when they are document dates
- Full names of natural persons (ФИО физлиц): стороны-физлица, подписанты-люди, «далее — Работник» if the name is specific
- Personal addresses of individuals if clearly private; keep organization legal address if it is the company's registered address

DISPLAY: In "content" strings use ONLY {{var_id}} markers for redacted spots — the UI will show a blank line (__________) there.

DO NOT remove or anonymize the employer/company party name if it is a legal entity — keep ТОО «…», АО, etc.

Split into logical sections (header, parties, subject, terms, signatures…). Each section "content" is plain text with {{placeholders}} embedded.

Variable types in "variables": "text", "date", "number", "multiline", "select". For "select" add "options".

Return ONLY valid JSON, no markdown.
""",
            temperature=0.3,
            max_tokens=3000,
        )

        content = response.content[0].text.strip()

        template_json = parse_llm_json(content)

        # Validate structure
        if not isinstance(template_json, dict):
            template_json = {"sections": []}

        if "sections" not in template_json:
            template_json["sections"] = []

        if "document_type" not in template_json:
            template_json["document_type"] = "Документ"

        return template_json

    except json.JSONDecodeError as e:
        import logging
        logging.error(f"Failed to parse Claude template response: {e}")
        # Return minimal valid template
        return {
            "document_type": "Документ",
            "sections": [
                {
                    "id": "content",
                    "title": "Содержание",
                    "order": 1,
                    "content": text[:2000],
                    "variables": [],
                }
            ],
        }

    except Exception as e:
        import logging
        logging.error(f"Error calling Claude for template generation: {e}")
        raise
