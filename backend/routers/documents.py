import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Document
from schemas import DocumentResponse, DocumentUpdate

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
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

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

    await db.delete(doc)
    await db.commit()

    return {"status": "deleted"}
