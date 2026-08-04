"""Registration/login (Phase 6.5). bcrypt password hashing, a short-lived JWT set as an
httpOnly cookie - no client-side token handling. Deliberately out of scope: email verification,
password reset, OAuth/social login - see docs/adr/0009-user-accounts.md.
"""

from __future__ import annotations

from auth import create_access_token, hash_password, verify_password
from config import get_settings
from db.postgres_client import get_postgres_connection
from dependencies import COOKIE_NAME, CurrentUser, get_current_user
from fastapi import APIRouter, Depends, HTTPException, Response, status
from psycopg2 import errors as pg_errors
from psycopg2.extensions import connection as PGConnection
from schemas import UserCreate, UserLogin, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

# 24h to match auth.ACCESS_TOKEN_EXPIRE_MINUTES - the cookie shouldn't outlive the JWT it carries.
_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24

_INSERT_USER_SQL = """
insert into users (email, password_hash)
values (%(email)s, %(password_hash)s)
returning id, email, created_at
"""

_SELECT_USER_SQL = """
select id, email, password_hash, created_at from users where email = %(email)s
"""


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate, conn: PGConnection = Depends(get_postgres_connection)
) -> UserPublic:
    with conn.cursor() as cur:
        try:
            cur.execute(
                _INSERT_USER_SQL,
                {"email": payload.email, "password_hash": hash_password(payload.password)},
            )
            row = cur.fetchone()
            conn.commit()
        except pg_errors.UniqueViolation:
            conn.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
    return UserPublic(**row)


@router.post("/login", response_model=UserPublic)
def login(
    payload: UserLogin,
    response: Response,
    conn: PGConnection = Depends(get_postgres_connection),
) -> UserPublic:
    with conn.cursor() as cur:
        cur.execute(_SELECT_USER_SQL, {"email": payload.email})
        row = cur.fetchone()

    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    token = create_access_token(
        user_id=row["id"], email=row["email"], secret=get_settings().jwt_secret
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE_SECONDS,
        # secure=True belongs here once the frontend is served over HTTPS - local dev is plain http.
    )
    return UserPublic(id=row["id"], email=row["email"], created_at=row["created_at"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME)


@router.get("/me", response_model=CurrentUser)
def me(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current_user
