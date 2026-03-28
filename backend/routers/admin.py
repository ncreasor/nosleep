from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import User, Document, AuditLog
from schemas import UserResponse, DocumentResponse, AuditLogResponse
from auth import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: User = Depends(get_current_user)):
    """Dependency: require admin role"""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    admin_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()


@router.patch("/users/{user_id}/role")
async def change_user_role(
    user_id: int,
    role: str,
    admin_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if role not in ("admin", "analyst"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.role = role
    await db.commit()
    await db.refresh(user)

    log = AuditLog(
        user_id=admin_user.id,
        action="admin.user.role_change",
        resource_type="user",
        resource_id=user_id,
        detail=f"Role changed to {role}",
    )
    db.add(log)
    await db.commit()

    return {"id": user.id, "email": user.email, "role": user.role}


@router.get("/documents", response_model=list[DocumentResponse])
async def list_all_documents(
    admin_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Document).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/audit-log", response_model=list[AuditLogResponse])
async def get_audit_log(
    admin_user: User = Depends(require_admin),
    action: str = None,
    resource_type: str = None,
    user_id: int = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()
