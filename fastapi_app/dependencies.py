"""FastAPI dependency for routes that need a logged-in user (Phase 7's feedback endpoint will
be the first consumer besides GET /auth/me). Stateless: decodes the httpOnly JWT cookie set by
routers/auth.py and trusts its claims - no DB round-trip per request.
"""

from __future__ import annotations

from auth import decode_access_token
from config import get_settings
from fastapi import HTTPException, Request, status
from jwt import PyJWTError
from pydantic import BaseModel

COOKIE_NAME = "access_token"


class CurrentUser(BaseModel):
    id: int
    email: str


def get_current_user(request: Request) -> CurrentUser:
    token = request.cookies.get(COOKIE_NAME)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_access_token(token, get_settings().jwt_secret)
    except PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from None
    return CurrentUser(id=int(payload["sub"]), email=payload["email"])


def get_optional_current_user(request: Request) -> CurrentUser | None:
    """Like get_current_user, but returns None instead of 401ing - for routes (GET /discover)
    that serve both anonymous and logged-in users differently rather than requiring a session."""
    token = request.cookies.get(COOKIE_NAME)
    if token is None:
        return None
    try:
        payload = decode_access_token(token, get_settings().jwt_secret)
    except PyJWTError:
        return None
    return CurrentUser(id=int(payload["sub"]), email=payload["email"])
