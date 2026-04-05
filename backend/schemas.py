from datetime import datetime
from pydantic import BaseModel, EmailStr


class DocumentCreate(BaseModel):
    title: str
    extracted_text: str | None = None
    folder_id: int | None = None
    filename: str | None = None


class DocumentUpdate(BaseModel):
    title: str | None = None
    extracted_text: str | None = None


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


class DocumentError(BaseModel):
    id: str
    type: str
    title: str
    original_text: str
    suggestion: str
    reason: str


class DocumentErrors(BaseModel):
    summary: str
    errors: list[DocumentError]


class DocumentCorrectionCreate(BaseModel):
    error_id: str | None = None
    error_type: str
    title: str | None = None
    original_text: str
    suggestion: str
    reason: str | None = None


class DocumentCorrectionResponse(BaseModel):
    id: int
    document_id: int
    user_id: int | None
    error_id: str | None
    error_type: str
    title: str | None
    original_text: str
    suggestion: str
    reason: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisStatistics(BaseModel):
    documents_analyzed: int = 0
    total_norms_found: int = 0
    grounded_norms: int = 0
    ungrounded_norms: int = 0
    avg_confidence: float | None = None
    by_verdict: dict[str, int] = {}


class UserStatisticsSummary(BaseModel):
    corrections_total: int
    corrections_by_type: dict[str, int]
    analysis: AnalysisStatistics | None = None


class DocumentSnapshotsPut(BaseModel):
    """Persisted JSON blobs for ИИ analysis and formulation/changes panels."""

    analysis: dict | None = None
    changes: dict | None = None


class DocumentSnapshotsGet(BaseModel):
    analysis: dict | None = None
    changes: dict | None = None


class DocumentAiChatMessagePost(BaseModel):
    message: str
    document_plain_text: str | None = None


class DocumentAiChatMessageIdBody(BaseModel):
    message_id: int
    document_plain_text: str | None = None


class AiChatProposedEdit(BaseModel):
    find: str
    replace: str
    reason: str | None = None


class AiChatMessageItem(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    assistant: dict | None = None


class DocumentAiChatStateResponse(BaseModel):
    chat_id: int
    messages: list[AiChatMessageItem]


class DocumentAiChatApproveResponse(BaseModel):
    ok: bool
    edits: list[AiChatProposedEdit]
    merged_plain: str | None = None
    detail: str | None = None


class DocumentAiChatOkResponse(BaseModel):
    ok: bool = True


class FolderCreate(BaseModel):
    name: str
    document_type: str
    description: str | None = None
    color: str | None = None


class FolderUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class FolderResponse(BaseModel):
    id: int
    user_id: int | None
    name: str
    document_type: str
    description: str | None = None
    color: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateFolderCreate(BaseModel):
    name: str
    description: str | None = None


class TemplateFolderUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class TemplateFolderResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateCreate(BaseModel):
    folder_id: int | None = None
    source_document_id: int | None = None
    name: str
    description: str | None = None
    content: str
    tags: str | None = None


class TemplateUpdate(BaseModel):
    folder_id: int | None = None
    name: str | None = None
    description: str | None = None
    content: str | None = None
    tags: str | None = None


class TemplateResponse(BaseModel):
    id: int
    user_id: int
    folder_id: int | None
    source_document_id: int | None = None
    name: str
    description: str | None = None
    content: str
    tags: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GenerateTemplateRequest(BaseModel):
    """Request to generate a template from a document"""
    folder_id: int | None = None
    name: str | None = None
