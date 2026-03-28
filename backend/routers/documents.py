import os
import uuid
import asyncio
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Document
from schemas import DocumentResponse, DocumentUpdate, DocumentSearchResult
from processing import background_process_document, get_qdrant_client, ensure_collection

router = APIRouter(prefix="/documents", tags=["documents"])
UPLOAD_DIR = Path("uploads")


async def ensure_upload_dir():
    UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    await ensure_upload_dir()

    file_id = str(uuid.uuid4())
    file_name = f"{file_id}_{file.filename}"
    file_path = UPLOAD_DIR / file_name

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
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

    asyncio.create_task(background_process_document(doc.id))

    return doc


@router.get("", response_model=list[DocumentResponse])
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document))
    return result.scalars().all()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: int,
    schema: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.title = schema.title
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete("/{document_id}")
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    await db.execute(delete(Document).where(Document.id == document_id))
    await db.commit()

    return {"status": "deleted"}


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    asyncio.create_task(background_process_document(document_id))
    return doc


@router.get("/search", response_model=list[DocumentSearchResult])
async def search_documents(q: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query too short")

    try:
        from processing import generate_embedding

        query_embedding = generate_embedding(q)
        client = get_qdrant_client()
        ensure_collection(client)

        results = client.search(
            collection_name="legal_documents",
            query_vector=query_embedding,
            limit=limit,
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
