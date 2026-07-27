"""Chat / RAG routes: ACL-filtered retrieval + Ollama generation."""
import json

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import auth
from app.audit import ACTION_QUERY, record_audit
from app.database import get_db
from app.ollama_client import generate_answer, stream_answer
from app.retrieval import RetrievedChunk, retrieve
from app.schemas import AskRequest, AskResponse, Citation

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    return [
        Citation(
            document_id=c.document_id,
            filename=c.filename,
            chunk_index=c.chunk_index,
            score=c.score,
            snippet=c.content[:240] + ("…" if len(c.content) > 240 else ""),
        )
        for c in chunks
    ]


def _audit_query(
    db: Session, current: auth.CurrentUser, query: str, chunks: list[RetrievedChunk]
) -> None:
    """Record which ACL-filtered documents this query was allowed to retrieve."""
    doc_ids = list(dict.fromkeys(c.document_id for c in chunks))
    doc_names = list(dict.fromkeys(c.filename for c in chunks))
    record_audit(
        db,
        actor_email=current.email,
        actor_roles=current.roles,
        action=ACTION_QUERY,
        query=query,
        document_ids=doc_ids,
        document_names=doc_names,
        num_results=len(chunks),
        detail=f"Retrieved {len(chunks)} chunk(s) from {len(doc_names)} document(s)",
    )


@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    current: auth.CurrentUser = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Answer a question over the ACL-filtered knowledge base (non-streaming)."""
    chunks = await run_in_threadpool(
        retrieve,
        db,
        payload.query,
        roles=current.roles,
        is_admin=current.is_admin,
        top_k=payload.top_k,
    )
    _audit_query(db, current, payload.query, chunks)
    answer = await generate_answer(payload.query, chunks)
    return AskResponse(answer=answer, citations=_citations(chunks))


@router.post("/ask/stream")
async def ask_stream(
    payload: AskRequest,
    current: auth.CurrentUser = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Streaming variant. Emits newline-delimited JSON events:

    {"type":"citations","data":[...]}  -> sent first
    {"type":"token","data":"..."}       -> one per token
    {"type":"done"}                      -> end of stream
    """
    chunks = await run_in_threadpool(
        retrieve,
        db,
        payload.query,
        roles=current.roles,
        is_admin=current.is_admin,
        top_k=payload.top_k,
    )
    # Audit the retrieval now (we already know what was returned) rather than
    # after streaming, so the record exists even if the client disconnects.
    _audit_query(db, current, payload.query, chunks)

    async def event_stream():
        citations = [c.model_dump() for c in _citations(chunks)]
        yield json.dumps({"type": "citations", "data": citations}) + "\n"
        async for token in stream_answer(payload.query, chunks):
            yield json.dumps({"type": "token", "data": token}) + "\n"
        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
