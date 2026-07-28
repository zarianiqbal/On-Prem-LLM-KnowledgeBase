"""In-memory sliding-window rate limiting.

Protects the expensive/abusable endpoints: chat questions are limited per user,
and login attempts per IP. Exceeding a limit returns HTTP 429 with a Retry-After
header.

This keeps its counters in process memory, so it's correct for a single-process
deployment (the local/self-hosted MVP). A multi-worker or multi-node deployment
would swap this for a shared store like Redis — the dependency interface below
stays the same.
"""
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status

from app import auth
from app.config import settings


class SlidingWindowLimiter:
    """Tracks a timestamp log per key and allows up to `limit` hits per `window`."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float) -> tuple[bool, float]:
        """Record a hit for `key`. Returns (allowed, retry_after_seconds)."""
        now = self._clock()
        cutoff = now - window
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= limit:
                # Retry once the oldest hit in the window rolls off.
                return False, max(hits[0] + window - now, 0.0)
            hits.append(now)
            return True, 0.0


# Shared limiter for the whole process. Scoped keys (e.g. "chat:alice@x.com")
# keep the different limits from colliding.
_limiter = SlidingWindowLimiter()


def _enforce(key: str, limit: int, window: int) -> None:
    if not settings.rate_limit_enabled:
        return
    allowed, retry_after = _limiter.check(key, limit, window)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down and try again shortly.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


def rate_limit_user(scope: str, limit: int, window: int):
    """Dependency: limit per authenticated user (keyed by email)."""

    def dependency(current: auth.CurrentUser = Depends(auth.get_current_user)):
        _enforce(f"{scope}:{current.email}", limit, window)

    return dependency


def rate_limit_ip(scope: str, limit: int, window: int):
    """Dependency: limit per client IP (for unauthenticated endpoints)."""

    def dependency(request: Request):
        ip = request.client.host if request.client else "unknown"
        _enforce(f"{scope}:{ip}", limit, window)

    return dependency
