from typing import Any

from google.auth.transport import requests
from google.oauth2 import id_token

from app.config import get_settings


def verify_google_id_token(token: str) -> dict[str, Any]:
    """Verify a Google Sign-In ID token and return the token claims."""
    settings = get_settings()
    info = id_token.verify_oauth2_token(
        token,
        requests.Request(),
        settings.google_client_id,
    )
    if not info.get("sub") or not info.get("email"):
        raise ValueError("Google token is missing sub or email")
    return info
