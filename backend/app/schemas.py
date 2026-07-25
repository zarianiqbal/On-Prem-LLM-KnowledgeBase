"""Pydantic request/response models (the API contract)."""
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---- Auth ----
class DevLoginRequest(BaseModel):
    email: EmailStr
    name: str = ""
    roles: list[str] = Field(default_factory=list)
    is_admin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    email: str
    name: str
    roles: list[str]
    is_admin: bool


class AuthConfig(BaseModel):
    """Which login methods the frontend should offer."""

    google_enabled: bool
    dev_login_enabled: bool


# ---- User management (admin) ----
class UserAdminOut(BaseModel):
    id: int
    email: str
    name: str
    roles: list[str]
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    roles: list[str] = Field(default_factory=list)
    is_admin: bool = False


# ---- Documents ----
class DocumentOut(BaseModel):
    id: int
    filename: str
    content_type: str
    uploaded_by: str
    allowed_roles: list[str]
    num_chunks: int
    created_at: datetime

    class Config:
        from_attributes = True


class IngestResponse(BaseModel):
    document: DocumentOut
    chunks_created: int


# ---- Chat / RAG ----
class AskRequest(BaseModel):
    query: str
    top_k: int | None = None


class Citation(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    score: float
    snippet: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
