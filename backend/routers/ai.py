from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from config import settings

router = APIRouter(prefix="/ai", tags=["ai"])

client = OpenAI(api_key=settings.openai_api_key)


class ChatRequest(BaseModel):
    messages: list[dict]
    system: str = "You are a helpful assistant."


class ChatStreamRequest(BaseModel):
    messages: list[dict]
    system: str = "You are a helpful assistant."


class EmbedRequest(BaseModel):
    text: str


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
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": request.system}] + request.messages,
            temperature=0.7,
        )
        return {
            "role": "assistant",
            "content": response.choices[0].message.content,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatStreamRequest):
    async def generate():
        try:
            stream = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "system", "content": request.system}] + request.messages,
                temperature=0.7,
                stream=True,
            )
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
