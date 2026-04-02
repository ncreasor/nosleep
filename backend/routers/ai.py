from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI
from qdrant_client.models import Filter, FieldCondition, MatchValue
import json
import logging
from config import settings
from database import get_db
from models import Chat, ChatMessage, Document
from auth import get_current_user
from processing import generate_embedding, get_qdrant_client, ensure_collection
from advanced_rag import AdvancedRAG
from multi_model import MultiModelEnsemble

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

client = OpenAI(api_key=settings.openai_api_key)


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
        response = client.models.retrieve(settings.openai_model)
        return {"status": "ok", "model": response.id}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        kwargs = {
            "model": settings.openai_model,
            "messages": [{"role": "system", "content": request.system}] + request.messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
        }
        if request.max_tokens:
            kwargs["max_tokens"] = request.max_tokens

        response = client.chat.completions.create(**kwargs)
        return {
            "role": "assistant",
            "content": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    async def generate():
        try:
            kwargs = {
                "model": settings.openai_model,
                "messages": [{"role": "system", "content": request.system}] + request.messages,
                "temperature": request.temperature,
                "top_p": request.top_p,
                "frequency_penalty": request.frequency_penalty,
                "presence_penalty": request.presence_penalty,
                "stream": True,
            }
            if request.max_tokens:
                kwargs["max_tokens"] = request.max_tokens

            stream = client.chat.completions.create(**kwargs)
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield f"data: {chunk.choices[0].delta.content}\n\n"
        except Exception as e:
            yield f"data: ERROR: {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/embed")
async def embed(request: EmbedRequest):
    try:
        response = client.embeddings.create(
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

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.7,
        )

        assistant_response = response.choices[0].message.content

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
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
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
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.7,
        )

        assistant_response = response.choices[0].message.content

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
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
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
                stream = client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[{"role": "system", "content": system_prompt}] + messages,
                    temperature=0.7,
                    stream=True,
                )

                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        full_response += token
                        await websocket.send_json({
                            "type": "token",
                            "content": token
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
    """Get detailed explanation of why a text is an error and how to fix it."""
    try:
        prompt = f"""You are a legal expert in Kazakh law. A user has found an error in a legal document.

Error title: {request.error_title}
Original text (incorrect): "{request.original_text}"
Suggested correction: "{request.suggestion}"
Reason: {request.reason}

Document context (first part): {request.document_context[:1000]}

Please provide:
1. A detailed explanation (2-3 sentences) of why the original text is wrong in the context of Kazakh law
2. A concrete example of how this error might affect the document
3. Any relevant legal references or rules that apply

Respond in Russian. Be concise and professional."""

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert in Kazakh law and legal document analysis. Provide clear, professional explanations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.5,
            max_tokens=600,
        )

        explanation = response.choices[0].message.content.strip()

        return {
            "explanation": explanation,
            "error_title": request.error_title,
            "original_text": request.original_text,
            "suggestion": request.suggestion
        }

    except Exception as e:
        logger.error(f"Error explaining error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Import AsyncSessionLocal for WebSocket
from database import AsyncSessionLocal
