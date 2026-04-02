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


class AnalyzeDocumentRequest(BaseModel):
    document_text: str


class CheckNormsRequest(BaseModel):
    norms: list[str]


@router.post("/analyze-legal-norms")
async def analyze_legal_norms(request: AnalyzeDocumentRequest):
    """
    Analyze document and extract all legal norm references.
    Uses GPT to intelligently identify Kazakhstan law articles and their context.
    """
    try:
        if not request.document_text or not isinstance(request.document_text, str):
            raise HTTPException(status_code=400, detail="document_text is required")

        # Truncate to avoid excessive token usage
        truncated = request.document_text[:4000]

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": """You are a legal document analyzer specializing in Kazakhstan legislation.
You understand Kazakh legal codes: ГК РК (Civil Code), ТК РК (Labor Code), УК РК (Criminal Code),
УПК РК, ГПК РК (Civil Procedure Code), КоАП РК, НК РК (Tax Code), ЗК РК (Land Code), ЖК РК (Housing Code), СК РК (Family Code).

Your task: Read the provided document text and find ALL references to Kazakhstan legal norms/articles.
For each reference found, provide comprehensive analysis including:
- When the norm was introduced
- All significant amendments with dates
- Whether it was replaced (and by what)
- Whether it was deleted
- Current legal status (valid/outdated/invalid)
- How this norm applies to the given document (applicability)
- Where and in what context it is mentioned in the document (usage_context)

Return ONLY valid JSON, no markdown or explanation.""",
                },
                {
                    "role": "user",
                    "content": f"""CRITICAL: Extract ONLY legal norm references that are EXPLICITLY MENTIONED in the document text.
Do NOT generate, invent, or hallucinate norms that are not in the text.
Do NOT create fictional statutes like "статья 888" or "статья 777" if they don't appear in the document.

Look for patterns like:
- "ст. 293 ТК РК"
- "статья 50 ТК РК"
- "ст. 100 ГК РК"
- "Закон РК от ..."

Document text:
---
{truncated}
---

For EACH reference explicitly found in the document, provide:
- norm_text: exact reference as written in document
- title, status, applicability, usage_context, introduced, amendments, replaced_by, deleted_at, current_status_explanation

IMPORTANT: If the reference text doesn't actually exist as a real norm in Kazakhstan legislation, mark status as "invalid".

Return as JSON:
{{
  "articles": [
    {{ "norm_text": "ст. 293 ТК РК", ... }}
  ]
}}

If ZERO norms are explicitly mentioned in the document, return {{"articles": []}}.
Do NOT invent any norms. Empty document = empty articles array.""",
                },
            ],
            temperature=0.3,
            max_tokens=3000,
        )

        content = response.choices[0].message.content.strip()

        try:
            json_response = json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse GPT response: {content}")
            return {"articles": []}

        # Validate response structure
        if not json_response.get("articles") or not isinstance(json_response["articles"], list):
            return {"articles": []}

        # Load Kazakhstan laws database for validation
        try:
            from laws_validator import validate_articles as validate_articles_fn

            validated = validate_articles_fn(json_response["articles"])
            return {"articles": validated}
        except Exception as e:
            logger.warning(f"Could not validate against laws database: {e}")
            return json_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing legal norms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-norms")
async def check_norms(request: CheckNormsRequest):
    """
    Check legal norm references for details, amendments, status, etc.
    Returns comprehensive information for each norm including chronology and related laws.
    """
    try:
        if not request.norms or not isinstance(request.norms, list):
            return {"results": {}}

        norms_text = '\n'.join([f'{i + 1}. "{n}"' for i, n in enumerate(request.norms)])

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": """You are a legal reference system specializing in the legislation of the Republic of Kazakhstan (RK/РК).
You have knowledge of Kazakh legal codes: ГК РК (Civil Code), ТК РК (Labor Code), УК РК (Criminal Code),
УПК РК, ГПК РК (Civil Procedure Code), КоАП РК, НК РК (Tax Code), ЗК РК (Land Code), ЖК РК (Housing Code), СК РК (Family Code).

For each legal norm reference provided, return a JSON object with:
- "status": one of "valid" (norm exists and is in force), "outdated" (norm exists but has been superseded or amended, or is from an old version), "invalid" (norm does not exist)
- "title": the official name/title of the article or law, null if unknown
- "introduced": ISO date string (YYYY-MM-DD) when the norm was first introduced, null if unknown
- "amendments": array of { "date": "YYYY-MM-DD", "description": "brief description in Russian" }, max 5, empty if none
- "current_status_explanation": 1-2 sentences in Russian explaining the current status
- "status_since": ISO date string (YYYY-MM-DD) when norm acquired its current status, null if unknown
- "replaced_by": string describing what replaced this norm (if status is "outdated"), null otherwise
- "is_latest_amendment": boolean true if using latest version, false if using older version
- "analysis": 2-3 sentence description in Russian of what this norm regulates, its scope, and who it applies to
- "related_laws": array of max 3 objects { "title": "official name", "number": "code abbreviation", "relevance": "brief explanation" } of related laws in the same domain
- "formulation_issues": array of max 3 objects { "type": "category", "description": "common mistake in Russian", "suggestion": "how to fix it" } - common errors when citing this norm in contracts/documents

Respond ONLY with valid JSON. No markdown, no explanation outside JSON.""",
                },
                {
                    "role": "user",
                    "content": f"""Check the following legal norm references from Kazakh legislation. For each, return a comprehensive analysis including status, title, chronology, detailed explanation, related laws, and common formulation issues.

Norms to check:
{norms_text}

Return as JSON object where each key is the norm reference text (exactly as provided):
{{ "norm1": {{ status, title, introduced, amendments, current_status_explanation, status_since, replaced_by, is_latest_amendment, analysis, related_laws, formulation_issues }}, "norm2": {{...}} }}""",
                },
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        content = response.choices[0].message.content.strip()

        try:
            json_response = json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse norm check response: {content}")
            return {"results": {}}

        return {"results": json_response}

    except Exception as e:
        logger.error(f"Error checking norms: {e}")
        raise HTTPException(status_code=500, detail=str(e))
