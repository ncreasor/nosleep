from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI
from qdrant_client.models import Filter, FieldCondition, MatchValue
from config import settings
from database import get_db
from models import Chat, ChatMessage, Document
from auth import get_current_user
from processing import generate_embedding, get_qdrant_client, ensure_collection

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
