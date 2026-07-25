"""Document routes: upload/ingest, list, delete."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.ingest import UnsupportedFileType, ingest_document
from app.models import Document
from app.retrieval import effective_roles
from app.schemas import DocumentOut, IngestResponse

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
    try:
        # Parsing + embedding is CPU-bound, so run it off the event loop.
        document = await run_in_threadpool(
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

    return IngestResponse(
        document=DocumentOut.model_validate(document),
        chunks_created=document.num_chunks,
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


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current: auth.CurrentUser = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.delete(doc)  # chunks cascade-delete
    db.commit()
