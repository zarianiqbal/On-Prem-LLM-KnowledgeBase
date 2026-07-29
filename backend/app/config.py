"""Application configuration, loaded from environment / .env file.

Everything is configurable so the same image can be shipped to any company —
they only edit their .env, never the code.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# The placeholder shipped in .env.example. Running in production with this value
# means anyone could forge tokens, so startup refuses it (see Settings below).
DEFAULT_JWT_SECRET = "change-me-to-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # "development" (default) or "production". In production the app refuses to
    # start with unsafe config (default secret, dev-login left on) — see
    # production_safety_errors().
    environment: str = "development"

    # Database
    database_url: str = (
        "postgresql+psycopg2://kb_user:kb_password@localhost:5432/knowledge_base"
    )

    # Auth / JWT
    jwt_secret: str = DEFAULT_JWT_SECRET
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
    # Hard ceiling on the client-supplied top_k, so a caller can't ask for a
    # huge number of chunks and blow up the prompt / DB work.
    max_retrieval_top_k: int = 20

    # --- Request limits (abuse / resource guards) ---
    max_upload_mb: int = 25  # reject uploads larger than this
    max_query_chars: int = 4000  # reject chat questions longer than this

    # Role given to any authenticated user who has no roles assigned. This is the
    # least-privileged tier (e.g. external customers): they see only public
    # documents plus anything explicitly tagged with this role.
    default_role: str = "customer"

    # LLM backend: "ollama" (real) or "mock" (canned demo output, no GPU needed).
    llm_provider: str = "ollama"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # --- Abuse hardening ---
    # Scan uploaded documents for prompt-injection phrases and flag suspicious
    # ones (they're still ingested, just recorded in the audit log as a warning).
    injection_scan_enabled: bool = True

    # In-memory sliding-window rate limiting. Keyed per user for chat and per IP
    # for login. Single-process only (fine for the local/self-hosted MVP).
    rate_limit_enabled: bool = True
    chat_rate_limit: int = 20  # max chat questions ...
    chat_rate_window: int = 60  # ... per this many seconds, per user
    login_rate_limit: int = 10  # max dev-login attempts ...
    login_rate_window: int = 60  # ... per this many seconds, per IP

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

    def production_safety_errors(self) -> list[str]:
        """Config that is unsafe to run in production. Empty list == safe.

        Checked at startup so a misconfigured deploy fails loudly instead of
        silently exposing a forgeable-token or self-serve-admin backdoor.
        """
        if self.environment.strip().lower() != "production":
            return []
        errors: list[str] = []
        if self.jwt_secret == DEFAULT_JWT_SECRET:
            errors.append(
                "JWT_SECRET is still the default value — set a strong random secret "
                '(python -c "import secrets; print(secrets.token_hex(32))").'
            )
        if self.dev_auth_enabled:
            errors.append(
                "DEV_AUTH_ENABLED must be false in production — dev-login lets any "
                "caller mint a token and self-assign admin."
            )
        return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
