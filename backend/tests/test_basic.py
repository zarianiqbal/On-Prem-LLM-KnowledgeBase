"""Lightweight tests that don't need Postgres, Ollama, or the embedding model."""
import asyncio
from types import SimpleNamespace

from app import auth
from app.config import settings
from app.ingest import chunk_text
from app.ollama_client import build_prompt, generate_answer
from app.retrieval import RetrievedChunk, effective_roles


def test_chunk_text_splits_long_text():
    text = " ".join(f"word{i}" for i in range(2000))
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(c.strip() for c in chunks)


def test_chunk_text_empty():
    assert chunk_text("   ") == []


def test_jwt_roundtrip_preserves_roles():
    user = SimpleNamespace(
        email="bob@example.com", name="Bob", roles=["hr", "finance"], is_admin=False
    )
    token = auth.create_access_token(user)

    creds = SimpleNamespace(credentials=token)
    current = auth.get_current_user(credentials=creds)

    assert current.email == "bob@example.com"
    assert current.roles == ["hr", "finance"]
    assert current.is_admin is False


def test_build_prompt_includes_context_and_injection_guard():
    chunks = [
        RetrievedChunk(
            document_id=1,
            filename="policy.pdf",
            chunk_index=0,
            content="Parental leave is 12 weeks.",
            score=0.91,
        )
    ]
    prompt = build_prompt("What is our parental leave policy?", chunks)
    assert "Parental leave is 12 weeks." in prompt
    assert "policy.pdf" in prompt
    assert "parental leave policy" in prompt.lower()


def test_build_prompt_handles_no_chunks():
    prompt = build_prompt("anything", [])
    assert "no relevant documents found" in prompt.lower()


def test_effective_roles_defaults_to_customer_when_empty():
    assert effective_roles([]) == [settings.default_role]
    assert effective_roles(["hr"]) == ["hr"]


def test_mock_llm_echoes_accessible_sources(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "mock")
    chunks = [
        RetrievedChunk(
            document_id=1,
            filename="handbook.pdf",
            chunk_index=0,
            content="Vacation is 20 days per year.",
            score=0.88,
        )
    ]
    answer = asyncio.run(generate_answer("How much vacation?", chunks))
    assert "Demo mode" in answer
    assert "handbook.pdf" in answer


def test_mock_llm_handles_no_accessible_chunks(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "mock")
    answer = asyncio.run(generate_answer("anything", []))
    assert "Demo mode" in answer
    assert "No documents you have access to matched" in answer
