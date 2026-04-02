import os
import uuid
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Document, User, AuditLog
from schemas import DocumentResponse, DocumentUpdate, DocumentSearchResult, DocumentAnalysis, DocumentInsights, DocumentCreate
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

router = APIRouter(prefix="/documents", tags=["documents"])
UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


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

    return doc


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

    return doc


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
    return result.scalars().all()


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
    return doc


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

    if not os.path.exists(doc.file_path):
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
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, Document.user_id == current_user.id
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc.title = schema.title
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
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

    if os.path.exists(doc.file_path):
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
    return doc


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
