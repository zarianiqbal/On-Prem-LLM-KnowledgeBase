"""Google OAuth client setup (via Authlib).

Registered only when GOOGLE_CLIENT_ID/SECRET are configured, so the app still
runs (with dev-login only) out of the box. Uses Google's OpenID Connect
discovery document, which gives us the user's email + name after login — nothing
else. No Drive access, no group reads.
"""
from authlib.integrations.starlette_client import OAuth

from app.config import settings

oauth = OAuth()

if settings.google_oauth_enabled:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url=(
            "https://accounts.google.com/.well-known/openid-configuration"
        ),
        client_kwargs={"scope": "openid email profile"},
    )
