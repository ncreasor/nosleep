import uuid
import logging
from typing import Optional
from pypdf import PdfReader
from docx import Document as DocxDocument
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from config import settings
from models import Document as DocumentModel
from database import AsyncSessionLocal

logger = logging.getLogger(__name__)
openai_client = OpenAI(api_key=settings.openai_api_key)


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client instance"""
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_service_api_key or None,
        timeout=30.0,
    )


def ensure_collection(client: QdrantClient, collection_name: str = "legal_documents", vector_size: int = 1536):
    """Create collection if it doesn't exist"""
    try:
        client.get_collection(collection_name)
    except Exception:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def extract_text(file_path: str, content_type: str) -> str:
    """Extract text from document"""
    if content_type == "application/pdf" or file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_path.endswith(".docx"):
        doc = DocxDocument(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()


def generate_embedding(text: str) -> list[float]:
    """Generate embedding using OpenAI"""
    response = openai_client.embeddings.create(
        model=settings.openai_embed_model,
        input=text[:8191],
    )
    return response.data[0].embedding


def classify_document(text: str, title: str) -> tuple[str, str]:
    """Classify document using GPT"""
    prompt = f"""You are a Kazakh/Russian legal document classifier.
Analyze this legal document and classify it as ONE of:
- "genuine": currently valid law/regulation
- "outdated": expired or superseded law
- "invalid": legally void or improperly formed

Document title: {title}
Document text (first 2000 chars):
{text[:2000]}

Return ONLY JSON in format: {{"classification": "genuine|outdated|invalid", "reason": "short reason"}}"""

    response = openai_client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=200,
    )

    try:
        import json
        result = json.loads(response.choices[0].message.content)
        classification = result.get("classification", "genuine")
        reason = result.get("reason", "")
        return classification, reason
    except Exception as e:
        logger.error(f"Classification parse error: {e}")
        return "genuine", "Could not classify"


async def process_document(document_id: int, db: AsyncSession) -> bool:
    """Process document: extract text, classify, embed, store in Qdrant"""
    try:
        result = await db.execute(select(DocumentModel).where(DocumentModel.id == document_id))
        doc = result.scalars().first()
        if not doc:
            logger.error(f"Document {document_id} not found")
            return False

        await db.execute(update(DocumentModel).where(DocumentModel.id == document_id).values(status="processing"))
        await db.commit()

        # Extract text
        text = extract_text(doc.file_path, doc.content_type)
        if not text or len(text.strip()) < 10:
            await db.execute(
                update(DocumentModel)
                .where(DocumentModel.id == document_id)
                .values(status="error", classification_reason="Could not extract text")
            )
            await db.commit()
            return False

        # Classify
        classification, reason = classify_document(text, doc.title)

        # Generate embedding
        embedding = generate_embedding(text)

        # Store in Qdrant (with fallback if Qdrant is unavailable)
        qdrant_id = str(uuid.uuid4())
        try:
            client = get_qdrant_client()
            ensure_collection(client)

            snippet = text[:300] if len(text) > 300 else text
            point = PointStruct(
                id=hash(qdrant_id) % (2**63 - 1),
                vector=embedding,
                payload={
                    "doc_id": document_id,
                    "title": doc.title,
                    "classification": classification,
                    "snippet": snippet,
                },
            )
            client.upsert("legal_documents", points=[point])
        except Exception as e:
            logger.warning(f"Failed to store in Qdrant: {e}, continuing without vector storage")

        # Update document
        await db.execute(
            update(DocumentModel)
            .where(DocumentModel.id == document_id)
            .values(
                status="ready",
                classification=classification,
                classification_reason=reason,
                qdrant_id=qdrant_id,
                extracted_text=text,
            )
        )
        await db.commit()
        logger.info(f"Document {document_id} processed successfully")
        return True

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
        try:
            await db.execute(
                update(DocumentModel)
                .where(DocumentModel.id == document_id)
                .values(status="error", classification_reason=str(e))
            )
            await db.commit()
        except:
            pass
        return False


async def background_process_document(document_id: int):
    """Background task wrapper for document processing"""
    async with AsyncSessionLocal() as db:
        await process_document(document_id, db)
