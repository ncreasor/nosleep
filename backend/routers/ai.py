from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from config import settings

router = APIRouter(prefix="/ai", tags=["ai"])

client = OpenAI(api_key=settings.openai_api_key)

PROMPTS = {
    "default": "You are a helpful assistant.",
    "document_analyzer": "Ты анализируешь документы. Выделяй ключевые моменты, суммируй информацию, давай полезные инсайты.",
    "technical_expert": "Ты технический эксперт. Объясняй сложные концепции просто и понятно.",
    "friendly": "Ты дружелюбный помощник. Отвечай с теплотой и используй эмодзи где уместно.",
}


class ChatRequest(BaseModel):
    messages: list[dict]
    mode: str = "default"
    document_text: str | None = None


class AnalyzeRequest(BaseModel):
    text: str
    mode: str = "document_analyzer"
    language: str = "ru"


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
    mode = request.mode if request.mode in PROMPTS else "default"
    system_prompt = PROMPTS[mode]

    messages = request.messages.copy()
    if request.document_text:
        messages.insert(0, {
            "role": "user",
            "content": f"[DOCUMENT CONTEXT]\n{request.document_text}\n[END CONTEXT]"
        })

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=0.7,
        )
        return {
            "role": "assistant",
            "content": response.choices[0].message.content,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    mode = request.mode if request.mode in PROMPTS else "default"
    system_prompt = PROMPTS[mode]

    messages = request.messages.copy()
    if request.document_text:
        messages.insert(0, {
            "role": "user",
            "content": f"[DOCUMENT CONTEXT]\n{request.document_text}\n[END CONTEXT]"
        })

    async def generate():
        try:
            stream = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                temperature=0.7,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield f"data: {chunk.choices[0].delta.content}\n\n"
        except Exception as e:
            yield f"data: ERROR: {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/analyze")
async def analyze(request: AnalyzeRequest):
    mode = request.mode if request.mode in PROMPTS else "document_analyzer"
    system_prompt = PROMPTS[mode]

    analysis_prompt = f"Проанализируй следующий текст на {request.language}:\n\n{request.text}"

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt},
            ],
            temperature=0.7,
        )
        return {
            "role": "assistant",
            "content": response.choices[0].message.content,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


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
