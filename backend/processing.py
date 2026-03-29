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
from legal_nlp import LegalNER, RelationExtractor, DocumentParser, DefinitionExtractor

logger = logging.getLogger(__name__)
openai_client = OpenAI(api_key=settings.openai_api_key)


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client instance"""
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_service_api_key or None,
        timeout=30.0,
    )


def ensure_collection(client: QdrantClient, collection_name: str = None, vector_size: int = 1536):
    if collection_name is None:
        collection_name = settings.qdrant_collection
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


def extract_metadata(text: str, title: str) -> dict:
    """Extract metadata from document using GPT"""
    prompt = f"""Analyze this legal document and extract metadata.

Document title: {title}
Document text (first 1000 chars):
{text[:1000]}

Return JSON with:
- category: one of "трудовое", "гражданское", "уголовное", "административное", "конституционное", "другое"
- law_date: ISO date (YYYY-MM-DD) if document has effective date, else null
- law_number: official number if mentioned (e.g. "№ 194-IV"), else null
- jurisdiction: country/region, default "Kazakhstan"

Return ONLY JSON."""

    try:
        response = openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150,
        )

        import json
        result = json.loads(response.choices[0].message.content)
        return {
            "category": result.get("category"),
            "law_date": result.get("law_date"),
            "law_number": result.get("law_number"),
            "jurisdiction": result.get("jurisdiction", "Kazakhstan"),
        }
    except Exception as e:
        logger.warning(f"Metadata extraction error: {e}")
        return {
            "category": None,
            "law_date": None,
            "law_number": None,
            "jurisdiction": "Kazakhstan",
        }


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


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks for RAG"""
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)

    return chunks


def extract_entities_from_document(text: str) -> dict:
    """Extract named entities from legal document."""
    try:
        entities = LegalNER.extract_entities(text)
        return {
            "total": len(entities),
            "persons": [e.text for e in entities if e.type.value == "person"],
            "organizations": [e.text for e in entities if e.type.value == "organization"],
            "dates": [e.text for e in entities if e.type.value == "date"],
            "amounts": [e.text for e in entities if e.type.value == "amount"],
            "law_references": [e.text for e in entities if e.type.value == "law_reference"],
            "articles": [e.text for e in entities if e.type.value == "article"],
        }
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return {"error": str(e)}


def extract_relations_from_document(text: str) -> dict:
    """Extract relations between entities."""
    try:
        relations = RelationExtractor.extract_relations(text)
        grouped = {}
        for rel in relations:
            if rel.relation_type not in grouped:
                grouped[rel.relation_type] = []
            grouped[rel.relation_type].append({
                "source": rel.source,
                "target": rel.target,
                "confidence": rel.confidence,
            })
        return {
            "total": len(relations),
            "by_type": grouped,
        }
    except Exception as e:
        logger.error(f"Relation extraction failed: {e}")
        return {"error": str(e)}


def parse_document_structure(text: str) -> dict:
    """Parse document into structured sections."""
    try:
        sections = DocumentParser.parse(text)
        toc = DocumentParser.get_toc(sections)
        return {
            "toc": toc,
            "sections_count": len(sections),
            "chapters": len([s for s in sections if s.section_type == "chapter"]),
            "articles": len([s for s in sections if s.section_type == "article"]),
        }
    except Exception as e:
        logger.error(f"Document parsing failed: {e}")
        return {"error": str(e)}


def extract_definitions(text: str) -> dict:
    """Extract key terms and definitions."""
    try:
        definitions = DefinitionExtractor.extract_definitions(text)
        return {
            "total": len(definitions),
            "definitions": definitions,
        }
    except Exception as e:
        logger.error(f"Definition extraction failed: {e}")
        return {"error": str(e)}


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

        # Extract metadata
        metadata = extract_metadata(text, doc.title)

        # Classify
        classification, reason = classify_document(text, doc.title)

        # Extract entities and relations for advanced analysis
        logger.info(f"Extracting entities for document {document_id}")
        entities_data = extract_entities_from_document(text)

        logger.info(f"Extracting relations for document {document_id}")
        relations_data = extract_relations_from_document(text)

        logger.info(f"Parsing document structure for {document_id}")
        structure_data = parse_document_structure(text)

        logger.info(f"Extracting definitions for document {document_id}")
        definitions_data = extract_definitions(text)

        # Generate embedding for main document
        embedding = generate_embedding(text[:8191])

        # Store in Qdrant (with fallback if Qdrant is unavailable)
        qdrant_id = str(uuid.uuid4())
        try:
            client = get_qdrant_client()
            ensure_collection(client)

            snippet = text[:300] if len(text) > 300 else text
            point = PointStruct(
                id=qdrant_id,
                vector=embedding,
                payload={
                    "doc_id": document_id,
                    "user_id": doc.user_id,
                    "title": doc.title,
                    "classification": classification,
                    "snippet": snippet,
                },
            )
            client.upsert(settings.qdrant_collection, points=[point])

            chunks = chunk_text(text)
            for idx, chunk in enumerate(chunks[:10]):
                chunk_embedding = generate_embedding(chunk)
                chunk_id = str(uuid.uuid4())
                chunk_point = PointStruct(
                    id=chunk_id,
                    vector=chunk_embedding,
                    payload={
                        "doc_id": document_id,
                        "user_id": doc.user_id,
                        "title": doc.title,
                        "chunk_index": idx,
                        "snippet": chunk[:200],
                    },
                )
                client.upsert(settings.qdrant_collection, points=[chunk_point])
        except Exception as e:
            logger.warning(f"Failed to store in Qdrant: {e}, continuing without vector storage")

        # Update document with metadata and classification
        await db.execute(
            update(DocumentModel)
            .where(DocumentModel.id == document_id)
            .values(
                status="ready",
                classification=classification,
                classification_reason=reason,
                category=metadata.get("category"),
                law_date=metadata.get("law_date"),
                law_number=metadata.get("law_number"),
                jurisdiction=metadata.get("jurisdiction"),
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
