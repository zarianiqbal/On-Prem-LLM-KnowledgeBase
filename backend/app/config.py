"""Application configuration, loaded from environment / .env file.

Everything is configurable so the same image can be shipped to any company —
they only edit their .env, never the code.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = (
        "postgresql+psycopg2://kb_user:kb_password@localhost:5432/knowledge_base"
    )

    # Auth / JWT
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    dev_auth_enabled: bool = True

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Chunking / retrieval
    chunk_size: int = 512
    chunk_overlap: int = 50
    retrieval_top_k: int = 5

    # Role given to any authenticated user who has no roles assigned. This is the
    # least-privileged tier (e.g. external customers): they see only public
    # documents plus anything explicitly tagged with this role.
    default_role: str = "customer"

    # LLM backend: "ollama" (real) or "mock" (canned demo output, no GPU needed).
    llm_provider: str = "ollama"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # CORS
    frontend_origin: str = "http://localhost:5173"

    # Google OAuth (optional)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # Comma-separated emails that are automatically granted admin on Google
    # login. Solves the bootstrap problem: the first admin can't be promoted by
    # another admin because none exists yet.
    admin_emails: str = ""

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
