from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Folder, Document
from schemas import FolderCreate, FolderUpdate, FolderResponse
from auth import get_current_user

router = APIRouter(prefix="/folders", tags=["folders"])


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    folder_data: FolderCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new folder for organizing documents by type."""
    new_folder = Folder(
        user_id=current_user.id,
        name=folder_data.name,
        document_type=folder_data.document_type,
        description=folder_data.description,
    )
    db.add(new_folder)
    await db.commit()
    await db.refresh(new_folder)
    return new_folder


@router.get("", response_model=list[FolderResponse])
async def list_folders(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all folders for current user."""
    result = await db.execute(
        select(Folder).where(Folder.user_id == current_user.id)
    )
    folders = result.scalars().all()
    return folders


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get folder details with document count."""
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id, Folder.user_id == current_user.id
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    return folder


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: int,
    folder_data: FolderUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update folder details."""
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id, Folder.user_id == current_user.id
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    if folder_data.name:
        folder.name = folder_data.name
    if folder_data.description is not None:
        folder.description = folder_data.description

    await db.commit()
    await db.refresh(folder)
    return folder


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete folder (documents will be orphaned, assign to another folder first)."""
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id, Folder.user_id == current_user.id
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    # Check if folder has documents
    doc_result = await db.execute(
        select(Document).where(Document.folder_id == folder_id)
    )
    if doc_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete folder with documents. Move them first.",
        )

    await db.execute(delete(Folder).where(Folder.id == folder_id))
    await db.commit()


@router.get("/{folder_id}/documents", response_model=list)
async def list_folder_documents(
    folder_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all documents in a folder."""
    # Verify folder exists and belongs to user
    folder_result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id, Folder.user_id == current_user.id
        )
    )
    folder = folder_result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    # Get documents in folder
    doc_result = await db.execute(
        select(Document).where(Document.folder_id == folder_id)
    )
    documents = doc_result.scalars().all()
    return documents
