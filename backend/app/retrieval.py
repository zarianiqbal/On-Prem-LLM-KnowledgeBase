"""ACL-filtered vector retrieval — the core of the privacy model.

The ACL filter is applied inside the SQL query, so chunks a user isn't allowed
to see are never even loaded, let alone sent to the LLM. Cosine distance on the
pgvector column gives semantic similarity.
"""
from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.embeddings import embed_text
from app.models import Chunk, Document


@dataclass
class RetrievedChunk:
    document_id: int
    filename: str
    chunk_index: int
    content: str
    score: float  # cosine similarity in [0, 1], higher is better


def effective_roles(roles: list[str]) -> list[str]:
    """A user with no assigned roles is treated as the least-privileged default
    role (e.g. `customer`), so they only ever see public + customer content."""
    return roles if roles else [settings.default_role]


def retrieve(
    db: Session,
    query: str,
    *,
    roles: list[str],
    is_admin: bool = False,
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Return the top_k most similar chunks the user is allowed to see."""
    # Clamp the client-supplied top_k into a sane range so a caller can't request
    # an enormous number of chunks (huge prompt / DB scan) or a non-positive one.
    k = top_k or settings.retrieval_top_k
    k = max(1, min(k, settings.max_retrieval_top_k))
    query_vector = embed_text(query)
    distance = Chunk.embedding.cosine_distance(query_vector)

    stmt = (
        db.query(
            Chunk.document_id,
            Document.filename,
            Chunk.chunk_index,
            Chunk.content,
            distance.label("distance"),
        )
        .join(Document, Document.id == Chunk.document_id)
    )

    # Admins bypass ACL; everyone else is restricted to chunks whose allowed_roles
    # overlap their effective roles (empty allowed_roles == public/everyone).
    if not is_admin:
        stmt = stmt.filter(
            or_(
                func.cardinality(Chunk.allowed_roles) == 0,
                Chunk.allowed_roles.overlap(effective_roles(roles)),
            )
        )

    rows = stmt.order_by(distance.asc()).limit(k).all()

    return [
        RetrievedChunk(
            document_id=row.document_id,
            filename=row.filename,
            chunk_index=row.chunk_index,
            content=row.content,
            score=round(1.0 - float(row.distance), 4),
        )
        for row in rows
    ]
