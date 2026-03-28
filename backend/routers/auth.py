from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import User, Chat, ChatMessage, AuditLog
from schemas import UserCreate, UserUpdate, UserResponse, Token
from auth import hash_password, verify_password, create_access_token, get_current_user
from config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed_password = hash_password(user_data.password)
    new_user = User(email=user_data.email, hashed_password=hashed_password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    log = AuditLog(
        user_id=new_user.id,
        action="user.register",
        resource_type="user",
        resource_id=new_user.id,
        detail=f"User registered: {new_user.email}",
    )
    db.add(log)
    await db.commit()

    return new_user


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.jwt_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_data.email:
        result = await db.execute(select(User).where(User.email == user_data.email, User.id != current_user.id))
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")
        current_user.email = user_data.email

    if user_data.password:
        current_user.hashed_password = hash_password(user_data.password)

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chats_result = await db.execute(select(Chat).where(Chat.user_id == current_user.id))
    chats = chats_result.scalars().all()
    for chat in chats:
        await db.execute(delete(ChatMessage).where(ChatMessage.chat_id == chat.id))

    await db.execute(delete(Chat).where(Chat.user_id == current_user.id))

    log = AuditLog(
        user_id=current_user.id,
        action="user.delete",
        resource_type="user",
        resource_id=current_user.id,
        detail=f"User deleted: {current_user.email}",
    )
    db.add(log)
    await db.commit()

    await db.execute(delete(User).where(User.id == current_user.id))
    await db.commit()
