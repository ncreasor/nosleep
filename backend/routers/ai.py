from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI
from qdrant_client.models import Filter, FieldCondition, MatchValue
import json
import logging
import anthropic
from config import settings
from database import get_db
from models import Chat, ChatMessage, Document
from auth import get_current_user
from processing import generate_embedding, get_qdrant_client, ensure_collection
from advanced_rag import AdvancedRAG
from multi_model import MultiModelEnsemble
from laws_rag import LawsRAG
from llm_json import parse_llm_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

# OpenAI client for embeddings only
openai_client = OpenAI(api_key=settings.openai_api_key)
# Anthropic Claude for LLM calls
claude_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


class ChatRequest(BaseModel):
    messages: list[dict]
    system: str = "You are a helpful assistant."
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0


class ChatStreamRequest(BaseModel):
    messages: list[dict]
    system: str = "You are a helpful assistant."
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0


class EmbedRequest(BaseModel):
    text: str
    language: str = "en"


class DocumentChatRequest(BaseModel):
    chat_id: int
    message: str


class AdvancedDocumentChatRequest(BaseModel):
    chat_id: int
    message: str
    document_id: int


@router.get("/ping")
async def ai_ping():
    try:
        # Test Claude client
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}]
        )
        return {"status": "ok", "model": "claude-haiku-4-5-20251001"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        kwargs = {
            "model": "claude-haiku-4-5-20251001",
            "messages": request.messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        if request.max_tokens:
            kwargs["max_tokens"] = request.max_tokens
        else:
            kwargs["max_tokens"] = 2048

        response = claude_client.messages.create(
            system=request.system,
            **kwargs
        )
        return {
            "role": "assistant",
            "content": response.content[0].text,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    async def generate():
        try:
            kwargs = {
                "model": "claude-haiku-4-5-20251001",
                "messages": request.messages,
                "temperature": request.temperature,
                "top_p": request.top_p,
            }
            if request.max_tokens:
                kwargs["max_tokens"] = request.max_tokens
            else:
                kwargs["max_tokens"] = 2048

            with claude_client.messages.stream(
                system=request.system,
                **kwargs
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {text}\n\n"
        except Exception as e:
            yield f"data: ERROR: {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/embed")
async def embed(request: EmbedRequest):
    try:
        response = openai_client.embeddings.create(
            model=settings.openai_embed_model,
            input=request.text,
        )
        return {
            "embedding": response.data[0].embedding,
            "model": response.model,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/document-chat")
async def document_chat(
    request: DocumentChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(Chat).where(Chat.id == request.chat_id, Chat.user_id == current_user.id)
        )
        chat = result.scalars().first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        msg_result = await db.execute(
            select(ChatMessage).where(ChatMessage.chat_id == request.chat_id).order_by(ChatMessage.created_at)
        )
        history = msg_result.scalars().all()

        system_prompt = "You are a helpful legal assistant for analyzing documents."
        context_text = ""

        if chat.document_id:
            doc_result = await db.execute(select(Document).where(Document.id == chat.document_id))
            doc = doc_result.scalars().first()
            if doc and doc.extracted_text:
                query_embedding = generate_embedding(request.message)
                qdrant_client = get_qdrant_client()
                ensure_collection(qdrant_client)

                filter_cond = Filter(
                    must=[FieldCondition(key="doc_id", match=MatchValue(value=doc.id))]
                )
                search_results = qdrant_client.search(
                    collection_name=settings.qdrant_collection,
                    query_vector=query_embedding,
                    limit=3,
                    query_filter=filter_cond,
                    with_payload=True,
                )

                snippets = [hit.payload.get("snippet", "") for hit in search_results if hit.payload.get("doc_id") == doc.id]
                if snippets:
                    context_text = "\n".join(snippets)

                system_prompt += f"\n\nDocument: {doc.title}\nClassification: {doc.classification or 'unknown'}\nRelevant excerpts:\n{context_text}"

        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in history
        ]
        messages.append({"role": "user", "content": request.message})

        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            messages=messages,
            system=system_prompt,
            temperature=0.7,
            max_tokens=2048,
        )

        assistant_response = response.content[0].text

        user_msg = ChatMessage(chat_id=request.chat_id, role="user", content=request.message)
        db.add(user_msg)
        await db.commit()

        assistant_msg = ChatMessage(chat_id=request.chat_id, role="assistant", content=assistant_response)
        db.add(assistant_msg)
        await db.commit()

        return {
            "role": "assistant",
            "content": assistant_response,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/document-chat/advanced")
async def advanced_document_chat(
    request: AdvancedDocumentChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Advanced RAG chat with query expansion, HyDE, hybrid search, and reranking."""
    try:
        result = await db.execute(
            select(Chat).where(Chat.id == request.chat_id, Chat.user_id == current_user.id)
        )
        chat = result.scalars().first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        doc_result = await db.execute(
            select(Document).where(Document.id == request.document_id)
        )
        doc = doc_result.scalars().first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        msg_result = await db.execute(
            select(ChatMessage).where(ChatMessage.chat_id == request.chat_id).order_by(ChatMessage.created_at)
        )
        history = msg_result.scalars().all()

        # Get embedding for query
        query_embedding = generate_embedding(request.message)

        # Prepare documents for RAG (in production, would fetch from Qdrant or DB)
        qdrant_client = get_qdrant_client()
        ensure_collection(qdrant_client)

        # Get all document chunks from Qdrant
        filter_cond = Filter(
            must=[FieldCondition(key="doc_id", match=MatchValue(value=doc.id))]
        )
        search_results = qdrant_client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_embedding,
            limit=50,
            query_filter=filter_cond,
            with_payload=True,
        )

        # Prepare documents for RAG pipeline
        documents = [
            {
                "id": hit.id,
                "title": doc.title,
                "content": hit.payload.get("snippet", ""),
            }
            for hit in search_results
        ]

        if not documents:
            documents = [{"id": doc.id, "title": doc.title, "content": doc.extracted_text or ""}]

        # Run advanced RAG pipeline
        rag = AdvancedRAG(qdrant_client)
        rag_result = rag.process_query(request.message, query_embedding, documents)

        # Prepare system prompt with RAG context
        system_prompt = f"""You are a helpful legal assistant for analyzing documents.
Document: {doc.title}
Classification: {doc.classification or 'unknown'}
Language: {doc.language or 'kk'}
Jurisdiction: {doc.jurisdiction or 'Kazakhstan'}

Confidence in retrieved context: {rag_result.confidence:.1%}
Query interpretations: {', '.join(rag_result.query_variants)}

Relevant excerpts from document:
{rag_result.answer}

Use the retrieved context to answer the user's question accurately. If the context doesn't contain relevant information, indicate this clearly."""

        # Build message history
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in history
        ]
        messages.append({"role": "user", "content": request.message})

        # Get LLM response with RAG context
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            messages=messages,
            system=system_prompt,
            temperature=0.7,
            max_tokens=2048,
        )

        assistant_response = response.content[0].text

        # Save messages to history
        user_msg = ChatMessage(chat_id=request.chat_id, role="user", content=request.message)
        db.add(user_msg)
        await db.commit()

        assistant_msg = ChatMessage(chat_id=request.chat_id, role="assistant", content=assistant_response)
        db.add(assistant_msg)
        await db.commit()

        return {
            "role": "assistant",
            "content": assistant_response,
            "model": response.model,
            "rag": {
                "confidence": rag_result.confidence,
                "sources": rag_result.sources,
                "query_variants": rag_result.query_variants,
            },
            "usage": {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/document-chat/ensemble")
async def ensemble_document_chat(
    request: AdvancedDocumentChatRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Multi-model ensemble chat: uses multiple LLMs for consensus-based answers."""
    try:
        result = await db.execute(
            select(Chat).where(Chat.id == request.chat_id, Chat.user_id == current_user.id)
        )
        chat = result.scalars().first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        msg_result = await db.execute(
            select(ChatMessage).where(ChatMessage.chat_id == request.chat_id).order_by(ChatMessage.created_at)
        )
        history = msg_result.scalars().all()

        system_prompt = "You are a helpful legal assistant. Provide accurate, concise answers."
        if request.document_id:
            doc_result = await db.execute(
                select(Document).where(Document.id == request.document_id)
            )
            doc = doc_result.scalars().first()
            if doc:
                system_prompt = f"""You are a legal assistant analyzing: {doc.title}
Classification: {doc.classification or 'unknown'}
Jurisdiction: {doc.jurisdiction or 'Kazakhstan'}

Provide accurate, well-reasoned answers based on the document context."""

        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in history
        ]
        messages.append({"role": "user", "content": request.message})

        # Run ensemble
        ensemble = MultiModelEnsemble()
        result = await ensemble.query_ensemble(system_prompt, messages)

        # Save to history
        user_msg = ChatMessage(chat_id=request.chat_id, role="user", content=request.message)
        db.add(user_msg)
        await db.commit()

        assistant_msg = ChatMessage(chat_id=request.chat_id, role="assistant", content=result.answer)
        db.add(assistant_msg)
        await db.commit()

        return MultiModelEnsemble.format_ensemble_response(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/chat/{chat_id}")
async def websocket_chat(websocket: WebSocket, chat_id: int):
    """WebSocket endpoint for real-time streaming chat with token-by-token responses."""
    await websocket.accept()
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")

            if not user_message:
                await websocket.send_json({"type": "error", "content": "Empty message"})
                continue

            try:
                # Get chat and history
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(Chat).where(Chat.id == chat_id))
                    chat = result.scalars().first()
                    if not chat:
                        await websocket.send_json({"type": "error", "content": "Chat not found"})
                        continue

                    msg_result = await db.execute(
                        select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.created_at)
                    )
                    history = msg_result.scalars().all()

                # Prepare messages
                messages = [
                    {"role": msg.role, "content": msg.content}
                    for msg in history[-10:]  # Last 10 messages for context
                ]
                messages.append({"role": "user", "content": user_message})

                system_prompt = "You are a helpful legal assistant. Provide concise, accurate answers."
                if chat.document_id:
                    async with AsyncSessionLocal() as db:
                        doc_result = await db.execute(select(Document).where(Document.id == chat.document_id))
                        doc = doc_result.scalars().first()
                        if doc:
                            system_prompt = f"You are a legal assistant analyzing: {doc.title}. Classification: {doc.classification or 'unknown'}"

                # Stream response
                await websocket.send_json({
                    "type": "start",
                    "message": "Generating response..."
                })

                full_response = ""
                with claude_client.messages.stream(
                    model="claude-haiku-4-5-20251001",
                    messages=messages,
                    system=system_prompt,
                    temperature=0.7,
                    max_tokens=2048,
                ) as stream:
                    for text in stream.text_stream:
                        full_response += text
                        await websocket.send_json({
                            "type": "token",
                            "content": text
                        })

                # Send completion
                await websocket.send_json({
                    "type": "end",
                    "content": "Response complete"
                })

                # Save to database
                async with AsyncSessionLocal() as db:
                    user_msg = ChatMessage(
                        chat_id=chat_id,
                        role="user",
                        content=user_message
                    )
                    db.add(user_msg)
                    await db.commit()

                    assistant_msg = ChatMessage(
                        chat_id=chat_id,
                        role="assistant",
                        content=full_response
                    )
                    db.add(assistant_msg)
                    await db.commit()

            except Exception as e:
                logger.error(f"Error in WebSocket chat: {e}")
                await websocket.send_json({
                    "type": "error",
                    "content": str(e)
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for chat {chat_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "content": "Connection error"})
        except:
            pass


class ExplainErrorRequest(BaseModel):
    error_title: str
    original_text: str
    suggestion: str
    reason: str
    document_context: str


@router.post("/explain-error")
async def explain_error(request: ExplainErrorRequest):
    """Get detailed explanation of why a text is an error — grounded in RAG evidence."""
    try:
        from laws_rag import LawsRAG

        # Search for relevant law text to ground the explanation
        rag = LawsRAG()
        search_query = f"{request.error_title} {request.original_text}"[:200]
        rag_context = ""
        try:
            rag_results = await rag.search(
                query=search_query, language="rus", top_k=3, use_reranking=False,
            )
            for r in rag_results:
                rag_context += f"--- {r['title']} ({r.get('number', '')}) ---\n"
                rag_context += f"Статус: {'действует' if r.get('is_active') else 'утратил силу'}\n"
                rag_context += f"{r['text'][:500]}\n\n"
        except Exception as rag_err:
            logger.warning("RAG search for explain-error failed: %s", rag_err)

        prompt = f"""Ты юридический эксперт по праву РК. Пользователь нашёл ошибку в юридическом документе.

Название ошибки: {request.error_title}
Оригинальный текст (некорректный): "{request.original_text}"
Предложенная правка: "{request.suggestion}"
Причина: {request.reason}

Контекст документа: {request.document_context[:1000]}

ФРАГМЕНТЫ ИЗ БАЗЫ ЗАКОНОДАТЕЛЬСТВА:
{rag_context if rag_context else "Релевантные нормы не найдены в базе."}

Объясни:
1. Почему оригинальный текст ошибочен (2-3 предложения) — ссылайся ТОЛЬКО на фрагменты из базы выше.
2. Конкретный пример того, как ошибка может повлиять на документ.
3. Ссылки на нормы — ТОЛЬКО те, что есть во фрагментах выше. Не выдумывай ссылки.

Если во фрагментах из базы нет подтверждения ошибки, честно укажи: "Не удалось подтвердить ошибку по базе законодательства."

Отвечай на русском. Кратко и профессионально."""

        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": prompt}],
            system="Ты эксперт по праву РК. Объясняешь ошибки ТОЛЬКО на основании предоставленных фрагментов из базы. Не выдумывай ссылки на нормы.",
            temperature=0.3,
            max_tokens=600,
        )

        explanation = response.content[0].text.strip()

        return {
            "explanation": explanation,
            "error_title": request.error_title,
            "original_text": request.original_text,
            "suggestion": request.suggestion,
            "grounded": bool(rag_context.strip()),
        }

    except Exception as e:
        logger.error(f"Error explaining error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class NormRemedyRequest(BaseModel):
    status: str
    norm_text: str = ""
    title: str = ""
    law_url: str | None = None
    law_chunk_preview: str | None = None
    usage_context: str = ""
    applicability: str = ""
    current_status_explanation: str = ""
    document_context: str = ""


@router.post("/remediate-norm")
async def remediate_norm(request: NormRemedyRequest):
    """
    Agent: produce concrete find/replace edits for plain document text, validated against the document.
    """
    try:
        doc = (request.document_context or "").strip()
        if not doc:
            return {
                "summary": "Нет текста документа для правки.",
                "edits": [],
                "skipped": [],
                "warnings": ["Пустой документ"],
            }

        doc = doc[:12000]
        kind = "устарела или заменена" if request.status == "outdated" else "недействительна или не применима"
        prompt = f"""Ты юридический агент по праву Республики Казахстан. Нужно исправить текст документа: убрать ссылки на норму, которая {kind}, и заменить формулировки на актуальные (по общим правилам ссылок на ТК/ГК РК и adilet.zan.kz).

Факты о проблемной норме:
- Статус: {request.status}
- Обозначение: {request.norm_text}
- Заголовок акта: {request.title}
- Ссылка adilet: {request.law_url or "нет"}
- Фрагмент из базы: {(request.law_chunk_preview or "")[:900]}
- Контекст в документе (откуда сопоставление): {(request.usage_context or "")[:900]}
- Пояснение статуса: {(request.current_status_explanation or "")[:600]}

ПОЛНЫЙ ТЕКСТ ДОКУМЕНТА (plain text, как есть, посимвольно важен перенос строк):
---
{doc}
---

Задача: верни ТОЛЬКО валидный JSON без markdown:
{{
  "summary": "одно короткое предложение что меняем и зачем",
  "edits": [
    {{
      "find": "подстрока из документа ВЫШЕ — скопируй буквально, без перефразирования",
      "replace": "на что заменить (можно пустая строка если удалить)",
      "reason": "кратко почему эта замена"
    }}
  ]
}}

Правила:
1. Каждое поле "find" ДОЛЖНО быть точной непрерывной подстрокой текста между --- (включая пробелы и переносы строк как в документе).
2. Не выдумывай цитаты — если точного фрагмента нет в документе, не добавляй такой edit.
3. Минимум правок, максимум пользы: ссылки на статьи, устаревшие номера законов, явные отсылки к отменённым актам.
4. Если в документе нет правимого текста по этой норме — верни "edits": [] и в summary объясни.
5. Порядок edits: сначала более длинные find (если несколько), чтобы не ломать вложенные замены; не пересекай find друг с другом."""

        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            messages=[{"role": "user", "content": prompt}],
            system="Ты возвращаешь только JSON с правками текста. Не добавляй текст вне JSON.",
            temperature=0.2,
            max_tokens=4096,
        )

        raw = response.content[0].text.strip()
        try:
            data = parse_llm_json(raw)
        except json.JSONDecodeError:
            logger.error("remediate_norm JSON parse failed: %s", raw[:500])
            raise HTTPException(status_code=502, detail="Модель вернула невалидный JSON")

        summary = (data.get("summary") or "").strip() or "Правки подготовлены."
        raw_edits = data.get("edits") if isinstance(data.get("edits"), list) else []

        validated: list[dict] = []
        skipped: list[dict] = []
        for i, ed in enumerate(raw_edits):
            if not isinstance(ed, dict):
                continue
            find = ed.get("find")
            replace = ed.get("replace")
            if find is None or replace is None:
                skipped.append({"index": i, "reason": "нет find или replace"})
                continue
            find = str(find)
            replace = str(replace)
            if not find:
                skipped.append({"index": i, "reason": "пустой find"})
                continue
            if find not in doc:
                skipped.append({"index": i, "reason": "find не найден в документе", "find": find[:80]})
                continue
            validated.append(
                {
                    "find": find,
                    "replace": replace,
                    "reason": (ed.get("reason") or "").strip(),
                }
            )

        validated.sort(key=lambda x: len(x["find"]), reverse=True)

        warnings: list[str] = []
        if skipped:
            warnings.append(f"Отброшено правок: {len(skipped)}")

        return {
            "summary": summary,
            "edits": validated,
            "skipped": skipped,
            "warnings": warnings,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remediate_norm: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Import AsyncSessionLocal for WebSocket
from database import AsyncSessionLocal


class ArticlesValidationRequest(BaseModel):
    articles: list[dict]


@router.post("/validate-articles")
async def validate_articles_handler(request: ArticlesValidationRequest):
    """
    Validate legal articles against Kazakh laws database
    Returns articles with status and information from real database
    """
    try:
        # Import here to avoid circular imports
        from laws_validator import validate_articles as validate_articles_fn

        validated_articles = validate_articles_fn(request.articles)
        return {"articles": validated_articles}
    except Exception as e:
        logger.error(f"Error validating articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class LawChronologyRequest(BaseModel):
    query: str
    title: str = ""
    sphere: str | None = None
    language: str = "rus"
    top_k: int = 15


@router.post("/law-chronology")
async def law_chronology(request: LawChronologyRequest):
    """
    Semantic search for related laws ordered by date from Qdrant payload.
    Returns a grounded timeline of related legislation.
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        from zeroentropy import ZeroEntropy

        ze = ZeroEntropy(api_key=settings.zeroentropy_api_key)
        qdrant = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_service_api_key or None,
            timeout=30.0,
        )

        # Embed query
        embed_resp = ze.models.embed(
            model="zembed-1",
            input=[request.query[:500]],
            input_type="document",
            dimensions=1280,
            encoding_format="float",
        )
        vector = embed_resp.results[0].embedding[:1280]

        # Build filter
        conditions = []
        if request.language:
            conditions.append(FieldCondition(key="language", match=MatchValue(value=request.language)))
        if request.sphere:
            conditions.append(FieldCondition(key="sphere", match=MatchValue(value=request.sphere)))
        flt = Filter(must=conditions) if conditions else None

        results = qdrant.search(
            collection_name=settings.qdrant_laws_collection,
            query_vector=vector,
            query_filter=flt,
            limit=request.top_k,
            with_payload=True,
            with_vectors=False,
        )

        # Deduplicate by title+number and collect entries
        seen: dict[str, dict] = {}
        for hit in results:
            p = hit.payload or {}
            title = (p.get("title") or "").strip()
            number = (p.get("number") or "").strip()
            key = f"{title}|{number}"
            if key in seen:
                continue
            date_raw = (p.get("date") or "").strip()
            seen[key] = {
                "title": title or "Норма РК",
                "number": number,
                "date": date_raw,
                "status": p.get("status", ""),
                "is_active": p.get("is_active", True),
                "sphere": p.get("sphere", ""),
                "text_preview": (p.get("text") or "")[:300].strip(),
                "url": p.get("url", ""),
                "relevance_score": round(float(hit.score), 4),
                "point_id": str(hit.id),
            }

        entries = list(seen.values())

        # Sort by date (entries with dates first, then by date ascending)
        def sort_key(e):
            d = e.get("date") or ""
            return (0 if d else 1, d)

        entries.sort(key=sort_key)

        # Split into current law versions and related laws
        # The first entry with highest relevance is likely the "main" match
        main_title = request.title.lower().strip() if request.title else ""
        timeline = []
        related = []
        for e in entries:
            e_title = e["title"].lower()
            # If the title contains a significant overlap with the query title, it's the same law
            if main_title and (main_title in e_title or e_title in main_title):
                timeline.append(e)
            else:
                related.append(e)

        # If nothing matched as "timeline", just put everything in timeline
        if not timeline:
            timeline = entries
            related = []

        return {
            "timeline": timeline,
            "related": related,
            "total": len(entries),
        }

    except Exception as e:
        logger.error(f"Error in law chronology: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AnalyzeDocumentRequest(BaseModel):
    document_text: str
    language: str = "rus"
    top_k_per_chunk: int = 5
    max_results: int = 28
    verify_facts: bool = True


class CheckNormsRequest(BaseModel):
    norms: list[str]


class LawsSearchRequest(BaseModel):
    query: str
    is_active: bool | None = None
    sphere: str | None = None
    language: str = "rus"
    doc_kind: str | None = None
    top_k: int = 5


@router.post("/laws-search")
async def laws_search(request: LawsSearchRequest):
    """
    Hybrid RAG search for Kazakhstan legal documents.
    Uses dense vectors (ZeroEntropy zembed-1) + BM25 + ZeRank reranking.
    Shows active/inactive status via payload indexes.
    """
    try:
        rag = LawsRAG()
        result = await rag.chat(
            query=request.query,
            is_active=request.is_active,
            sphere=request.sphere,
            language=request.language,
            top_k=request.top_k,
        )

        return {
            "answer": result["answer"],
            "sources": result["results"],
            "sources_count": result["sources_count"],
            "model": "claude-haiku-4-5-20251001",
        }
    except Exception as e:
        logger.error(f"Error in laws search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-legal-norms")
async def analyze_legal_norms(request: AnalyzeDocumentRequest):
    """
    Embed document chunks (zembed-1), search Qdrant `zan_legal_docs`, optionally
    verify each chunk against top-k candidates with Claude (grounding).
    """
    try:
        if not request.document_text or not isinstance(request.document_text, str):
            raise HTTPException(status_code=400, detail="document_text is required")

        from document_law_match import match_document_to_laws

        result = await match_document_to_laws(
            request.document_text,
            language=request.language,
            top_k_per_chunk=request.top_k_per_chunk,
            max_results=request.max_results,
            verify_facts=request.verify_facts,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing legal norms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-norms")
async def check_norms(request: CheckNormsRequest):
    """
    Check legal norm references — grounded in local DB + Qdrant RAG.
    Only returns facts that can be substantiated by retrieved evidence.
    """
    try:
        if not request.norms or not isinstance(request.norms, list):
            return {"results": {}}

        from laws_validator import validate_norm
        from laws_rag import LawsRAG

        rag = LawsRAG()
        results: dict[str, dict] = {}

        for norm_ref in request.norms:
            # Step 1: Check local law database (ground truth)
            db_result = validate_norm(norm_ref)

            # Step 2: Search Qdrant for actual law text
            rag_results = await rag.search(
                query=norm_ref, language="rus", top_k=3, use_reranking=False,
            )
            rag_context = ""
            rag_sources = []
            for r in rag_results:
                rag_context += f"--- {r['title']} ({r.get('number', '')}) ---\n"
                rag_context += f"Статус: {'действует' if r.get('is_active') else 'утратил силу'}\n"
                rag_context += f"Текст: {r['text'][:600]}\n\n"
                rag_sources.append({
                    "title": r.get("title", ""),
                    "number": r.get("number", ""),
                    "is_active": r.get("is_active", False),
                    "url": r.get("url", ""),
                })

            # Step 3: Build result from DB facts first
            entry: dict = {
                "status": db_result.get("status", "invalid"),
                "title": db_result.get("title"),
                "introduced": db_result.get("introduced"),
                "amendments": [],
                "current_status_explanation": "",
                "status_since": None,
                "replaced_by": None,
                "is_latest_amendment": None,
                "analysis": "",
                "related_laws": [],
                "formulation_issues": [],
                "grounded": db_result.get("valid", False),
                "source": "database" if db_result.get("valid") else "not_found",
                "rag_sources": rag_sources,
            }

            if not db_result.get("valid"):
                entry["current_status_explanation"] = db_result.get("reason") or "Норма не найдена в локальной базе данных."

            # Step 4: If we have RAG context, ask Claude to analyze ONLY from evidence
            if rag_context.strip():
                entry["source"] = "database+rag" if db_result.get("valid") else "rag_only"
                try:
                    response = claude_client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        messages=[{
                            "role": "user",
                            "content": f"""Проанализируй норму "{norm_ref}" ТОЛЬКО на основании приведённых ниже фрагментов из базы законодательства РК.

Результат проверки по локальной базе:
- Статус: {db_result.get('status', 'unknown')}
- Название статьи: {db_result.get('title') or 'не найдено'}
- Закон: {db_result.get('law_name') or 'не определён'}

Фрагменты из базы Qdrant:
{rag_context}

ВАЖНО:
- НЕ выдумывай поправки, даты или замены — если информации нет в фрагментах выше, пиши null.
- Поле "analysis" — только то, что следует из текста фрагментов.
- "amendments" — только если в тексте явно упомянуты изменения.
- Если норма не найдена ни в базе, ни во фрагментах — status: "invalid".

Верни ТОЛЬКО JSON:
{{
  "current_status_explanation": "1-2 предложения на основе фрагментов",
  "analysis": "2-3 предложения о предмете регулирования на основе фрагментов, или пустая строка если нет данных",
  "amendments": [],
  "replaced_by": null,
  "formulation_issues": []
}}""",
                        }],
                        system="Ты юридический справочник РК. Отвечай ТОЛЬКО на основании предоставленных фрагментов. Не придумывай факты. Отвечай только валидным JSON.",
                        temperature=0.1,
                        max_tokens=800,
                    )

                    llm_data = parse_llm_json(response.content[0].text.strip())
                    if isinstance(llm_data, dict):
                        if llm_data.get("current_status_explanation"):
                            entry["current_status_explanation"] = llm_data["current_status_explanation"]
                        if llm_data.get("analysis"):
                            entry["analysis"] = llm_data["analysis"]
                        if isinstance(llm_data.get("amendments"), list):
                            entry["amendments"] = llm_data["amendments"]
                        if llm_data.get("replaced_by"):
                            entry["replaced_by"] = llm_data["replaced_by"]
                        if isinstance(llm_data.get("formulation_issues"), list):
                            entry["formulation_issues"] = llm_data["formulation_issues"]
                except Exception as llm_err:
                    logger.warning("LLM enrichment for norm %s failed: %s", norm_ref, llm_err)

            results[norm_ref] = entry

        return {"results": results}

    except Exception as e:
        logger.error(f"Error checking norms: {e}")
        raise HTTPException(status_code=500, detail=str(e))
