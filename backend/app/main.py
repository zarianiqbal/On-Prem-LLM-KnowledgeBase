"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, chat, documents, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the pgvector extension + tables on startup.
    init_db()
    yield


app = FastAPI(
    title="On-Prem LLM Knowledge Base",
    version="0.1.0",
    description="Privacy-first RAG: the LLM only ever sees ACL-filtered chunks.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authlib stores the OAuth state/nonce in a signed session cookie during the
# redirect round-trip to Google.
app.add_middleware(SessionMiddleware, secret_key=settings.jwt_secret, same_site="lax")

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(users.router)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "model": settings.ollama_model}
