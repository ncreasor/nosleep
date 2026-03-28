from datetime import datetime
from pydantic import BaseModel, EmailStr


class DocumentCreate(BaseModel):
    title: str


class DocumentUpdate(BaseModel):
    title: str


class DocumentResponse(BaseModel):
    id: int
    title: str
    filename: str
    content_type: str
    size: int
    status: str
    classification: str | None = None
    classification_reason: str | None = None
    category: str | None = None
    law_date: datetime | None = None
    law_number: str | None = None
    jurisdiction: str | None = None
    language: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentSearchResult(BaseModel):
    id: int
    title: str
    classification: str | None
    score: float
    snippet: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    terms_agreed: bool


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class ChatMessageCreate(BaseModel):
    role: str
    content: str


class ChatMessageResponse(BaseModel):
    id: int
    chat_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatCreate(BaseModel):
    title: str | None = None
    document_id: int | None = None


class ChatUpdate(BaseModel):
    title: str


class ChatResponse(BaseModel):
    id: int
    title: str
    document_id: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatWithMessages(ChatResponse):
    messages: list[ChatMessageResponse]


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    action: str
    resource_type: str
    resource_id: int | None
    detail: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentAnalysis(BaseModel):
    """Detailed analysis of a legal document."""
    entities: dict
    relations: dict
    structure: dict
    definitions: dict


class DocumentInsights(BaseModel):
    """Comprehensive document insights."""
    document_id: int
    title: str
    classification: str | None
    entities_count: int
    relations_count: int
    sections_count: int
    definitions_count: int
    key_terms: list[str]


class FolderCreate(BaseModel):
    name: str
    document_type: str
    description: str | None = None


class FolderUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class FolderResponse(BaseModel):
    id: int
    user_id: int | None
    name: str
    document_type: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
