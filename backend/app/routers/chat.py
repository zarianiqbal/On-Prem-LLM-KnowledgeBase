"""Chat / RAG routes: ACL-filtered retrieval + Ollama generation."""
import json

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app import auth
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

    async def event_stream():
        citations = [c.model_dump() for c in _citations(chunks)]
        yield json.dumps({"type": "citations", "data": citations}) + "\n"
        async for token in stream_answer(payload.query, chunks):
            yield json.dumps({"type": "token", "data": token}) + "\n"
        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
