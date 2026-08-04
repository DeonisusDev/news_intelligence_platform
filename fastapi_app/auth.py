"""Password hashing and JWT issuance/validation for Phase 6.5 auth. Deliberately free of
FastAPI/DB imports so it's unit-testable in isolation (see tests/fastapi_app/test_auth.py) -
routers/auth.py and dependencies.py are the only callers.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

ALGORITHM = "HS256"
# Short-lived, no refresh tokens - re-login after expiry. Deliberately simple for a portfolio
# project; see docs/adr/0009-user-accounts.md.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(*, user_id: int, email: str, secret: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=[ALGORITHM])
