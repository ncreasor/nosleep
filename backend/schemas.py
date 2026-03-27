from datetime import datetime
from pydantic import BaseModel


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
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
