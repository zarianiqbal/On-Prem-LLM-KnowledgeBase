"""SQLAlchemy ORM models.

Security model lives here: every Chunk carries `allowed_roles`. Retrieval
filters on this column *before* anything reaches the LLM, so a user can never
retrieve a chunk their role isn't allowed to see.
"""
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    # Roles map to Google Workspace groups, e.g. ["hr", "engineering"].
    roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="")
    uploaded_by: Mapped[str] = mapped_column(String(320), default="")
    # Which roles are allowed to see chunks from this document.
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    num_chunks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # Denormalized from the parent document for fast, single-query ACL filtering.
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))

    document: Mapped["Document"] = relationship(back_populates="chunks")


class AuditLog(Base):
    """An append-only record of every security-relevant action.

    The important case is a `query`: we record which ACL-filtered documents were
    returned to the asking user, so an admin can later prove the access boundary
    held — a user only ever saw documents their roles permit.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )
    # Who performed the action, and the roles they held at that moment (roles can
    # change over time, so we snapshot them here rather than joining to users).
    actor_email: Mapped[str] = mapped_column(String(320), index=True)
    actor_roles: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    # One of the ACTION_* constants in app/audit.py.
    action: Mapped[str] = mapped_column(String(32), index=True)
    # Human-readable summary, e.g. "Uploaded 'handbook.pdf' (hr), 12 chunks".
    detail: Mapped[str] = mapped_column(Text, default="")
    # The question asked (query actions only).
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Documents involved: the chunks returned for a query, or the doc up/deleted.
    document_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    document_names: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    # How many chunks a query returned (null for non-query actions).
    num_results: Mapped[int | None] = mapped_column(Integer, nullable=True)
