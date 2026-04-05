import json
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models import Template, TemplateFolder
from processing import extract_text
from schemas import (
    TemplateFolderCreate,
    TemplateFolderUpdate,
    TemplateFolderResponse,
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
)
from auth import get_current_user

router = APIRouter(prefix="/templates", tags=["templates"])


# ============= Template Folders =============


@router.post("/folders", response_model=TemplateFolderResponse, status_code=status.HTTP_201_CREATED)
async def create_template_folder(
    folder_data: TemplateFolderCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new template folder."""
    new_folder = TemplateFolder(
        user_id=current_user.id,
        name=folder_data.name,
        description=folder_data.description,
    )
    db.add(new_folder)
    await db.commit()
    await db.refresh(new_folder)
    return new_folder


@router.get("/folders", response_model=list[TemplateFolderResponse])
async def list_template_folders(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all template folders for current user."""
    result = await db.execute(
        select(TemplateFolder).where(TemplateFolder.user_id == current_user.id)
    )
    folders = result.scalars().all()
    return folders


@router.get("/folders/{folder_id}", response_model=TemplateFolderResponse)
async def get_template_folder(
    folder_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get template folder details."""
    result = await db.execute(
        select(TemplateFolder).where(
            TemplateFolder.id == folder_id, TemplateFolder.user_id == current_user.id
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    return folder


@router.patch("/folders/{folder_id}", response_model=TemplateFolderResponse)
async def update_template_folder(
    folder_id: int,
    folder_data: TemplateFolderUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update template folder."""
    result = await db.execute(
        select(TemplateFolder).where(
            TemplateFolder.id == folder_id, TemplateFolder.user_id == current_user.id
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


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template_folder(
    folder_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete template folder (templates will be orphaned)."""
    result = await db.execute(
        select(TemplateFolder).where(
            TemplateFolder.id == folder_id, TemplateFolder.user_id == current_user.id
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    await db.execute(delete(TemplateFolder).where(TemplateFolder.id == folder_id))
    await db.commit()


# ============= Templates =============


@router.post("/from-docx")
@router.post("/from-word")
async def template_extract_word(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """Extract plain text from .docx (python-docx) or .doc (antiword / catdoc / LibreOffice)."""

    name_lower = (file.filename or "").lower()
    if not (name_lower.endswith(".docx") or name_lower.endswith(".doc")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поддерживаются только файлы .doc и .docx",
        )
    content = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Max {settings.max_file_size_mb} MB",
        )
    suffix = ".docx" if name_lower.endswith(".docx") else ".doc"
    mime = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if suffix == ".docx"
        else "application/msword"
    )
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        with open(path, "wb") as f:
            f.write(content)
        try:
            text = extract_text(path, mime)
        except RuntimeError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            ) from e
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return {"text": text or "", "filename": file.filename}


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new template."""
    # Verify folder exists if provided
    if template_data.folder_id:
        folder_result = await db.execute(
            select(TemplateFolder).where(
                TemplateFolder.id == template_data.folder_id,
                TemplateFolder.user_id == current_user.id,
            )
        )
        if not folder_result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")

    new_template = Template(
        user_id=current_user.id,
        folder_id=template_data.folder_id,
        name=template_data.name,
        description=template_data.description,
        content=template_data.content,
        tags=template_data.tags,
    )
    db.add(new_template)
    await db.commit()
    await db.refresh(new_template)
    return new_template


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    folder_id: int | None = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all templates for current user (optionally filtered by folder)."""
    query = select(Template).where(Template.user_id == current_user.id)
    if folder_id is not None:
        query = query.where(Template.folder_id == folder_id)

    result = await db.execute(query)
    templates = result.scalars().all()
    return templates


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get template details."""
    result = await db.execute(
        select(Template).where(
            Template.id == template_id, Template.user_id == current_user.id
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    template_data: TemplateUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update template."""
    result = await db.execute(
        select(Template).where(
            Template.id == template_id, Template.user_id == current_user.id
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if template_data.name:
        template.name = template_data.name
    if template_data.description is not None:
        template.description = template_data.description
    if template_data.content is not None:
        try:
            old = json.loads(template.content) if template.content else {}
            new = json.loads(template_data.content)
            if (
                isinstance(old, dict)
                and isinstance(new, dict)
                and old.get("structured")
                and "structured" not in new
            ):
                new["structured"] = old["structured"]
            template.content = json.dumps(new, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            template.content = template_data.content
    if template_data.folder_id is not None:
        template.folder_id = template_data.folder_id
    if template_data.tags is not None:
        template.tags = template_data.tags

    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete template."""
    result = await db.execute(
        select(Template).where(
            Template.id == template_id, Template.user_id == current_user.id
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    await db.execute(delete(Template).where(Template.id == template_id))
    await db.commit()
