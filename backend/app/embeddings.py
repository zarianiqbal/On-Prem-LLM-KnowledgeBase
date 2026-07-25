"""Local embedding model wrapper (sentence-transformers).

Loaded lazily on first use so the app starts fast and tests can import modules
without downloading a model. Runs fully on-prem — text never leaves the machine.
"""
from functools import lru_cache

from app.config import settings


@lru_cache
def _get_model():
    # Imported here (not at module top) so the heavy dependency loads only when
    # embeddings are actually needed.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts into vectors."""
    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return [v.tolist() for v in vectors]


def embed_text(text: str) -> list[float]:
    """Embed a single text into one vector."""
    return embed_texts([text])[0]
