from datetime import datetime

from pydantic import BaseModel, Field


class RenameDocumentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)


class DocumentResponse(BaseModel):
    id: int
    filename: str
    category: str
    url: str | None = None
    cloudinary_url: str | None = None
    preview_url: str | None = None
    created_at: datetime | None = None


class DocumentDetailResponse(BaseModel):
    status: str
    data: DocumentResponse


class DocumentListResponse(BaseModel):
    status: str
    data: list[DocumentResponse]

