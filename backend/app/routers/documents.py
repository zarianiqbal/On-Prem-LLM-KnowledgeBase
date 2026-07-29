"""Document routes: upload/ingest, list, delete."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app import auth
from app.audit import ACTION_DELETE, ACTION_RETAG, ACTION_UPLOAD, record_audit
from app.config import settings
from app.database import get_db
from app.ingest import UnsupportedFileType, ingest_document
from app.models import Chunk, Document
from app.retrieval import effective_roles
from app.schemas import DocumentOut, DocumentUpdate, IngestResponse

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    allowed_roles: str = Form(""),
    current: auth.CurrentUser = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    """Upload a document and make it searchable. Admin only.

    `allowed_roles` is a comma-separated list, e.g. "hr,finance". Empty means the
    document is visible to all authenticated users.
    """
    roles = [r.strip() for r in allowed_roles.split(",") if r.strip()]
    data = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large (max {settings.max_upload_mb} MB).",
        )
    try:
        # Parsing + embedding is CPU-bound, so run it off the event loop.
        document, warnings = await run_in_threadpool(
            ingest_document,
            db,
            filename=file.filename,
            content_type=file.content_type or "",
            data=data,
            allowed_roles=roles,
            uploaded_by=current.email,
        )
    except UnsupportedFileType as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    detail = (
        f"Uploaded '{document.filename}' "
        f"({', '.join(roles) or 'everyone'}), {document.num_chunks} chunks"
    )
    if warnings:
        detail += f" — ⚠ possible prompt injection: {', '.join(warnings)}"
    record_audit(
        db,
        actor_email=current.email,
        actor_roles=current.roles,
        action=ACTION_UPLOAD,
        document_ids=[document.id],
        document_names=[document.filename],
        detail=detail,
    )
    return IngestResponse(
        document=DocumentOut.model_validate(document),
        chunks_created=document.num_chunks,
        warnings=warnings,
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    current: auth.CurrentUser = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """List documents. Admins see all; users see only what their roles allow."""
    q = db.query(Document)
    if not current.is_admin:
        docs = q.all()
        roles = set(effective_roles(current.roles))
        return [
            DocumentOut.model_validate(d)
            for d in docs
            if not d.allowed_roles or roles.intersection(d.allowed_roles)
        ]
    return [DocumentOut.model_validate(d) for d in q.all()]


@router.patch("/{document_id}", response_model=DocumentOut)
def retag_document(
    document_id: int,
    payload: DocumentUpdate,
    current: auth.CurrentUser = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    """Change which roles may see a document, after upload. Admin only.

    The ACL tag is denormalized onto every chunk for fast filtering, so we update
    the document and all of its chunks in one transaction to keep them in sync.
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    roles = [r.strip() for r in payload.allowed_roles if r.strip()]
    old_roles = list(doc.allowed_roles or [])
    doc.allowed_roles = roles
    db.query(Chunk).filter(Chunk.document_id == doc.id).update(
        {Chunk.allowed_roles: roles}, synchronize_session=False
    )
    db.commit()
    db.refresh(doc)
    record_audit(
        db,
        actor_email=current.email,
        actor_roles=current.roles,
        action=ACTION_RETAG,
        document_ids=[doc.id],
        document_names=[doc.filename],
        detail=(
            f"Re-tagged '{doc.filename}': "
            f"{old_roles or 'everyone'} -> {roles or 'everyone'}"
        ),
    )
    return DocumentOut.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current: auth.CurrentUser = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Capture identity before the row is gone, for the audit record.
    deleted_id, deleted_name = doc.id, doc.filename
    db.delete(doc)  # chunks cascade-delete
    db.commit()
    record_audit(
        db,
        actor_email=current.email,
        actor_roles=current.roles,
        action=ACTION_DELETE,
        document_ids=[deleted_id],
        document_names=[deleted_name],
        detail=f"Deleted '{deleted_name}'",
    )
