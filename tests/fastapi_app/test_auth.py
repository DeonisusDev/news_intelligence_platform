"""Auth tests (Phase 6.5): pure unit tests for password hashing/JWT (no DB, no HTTP), plus
endpoint tests against a fake in-memory Postgres users table (see conftest.py's
FakeUsersConnection).
"""

import jwt as pyjwt
import pytest
from auth import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_password_is_not_the_plaintext():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"


def test_verify_password_accepts_the_matching_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_password_rejects_a_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_create_and_decode_access_token_round_trips():
    token = create_access_token(user_id=42, email="user@example.com", secret="s3cr3t")
    payload = decode_access_token(token, "s3cr3t")
    assert payload["sub"] == "42"
    assert payload["email"] == "user@example.com"


def test_decode_access_token_rejects_a_token_signed_with_a_different_secret():
    token = create_access_token(user_id=42, email="user@example.com", secret="s3cr3t")
    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token(token, "a-different-secret")


def test_register_creates_a_user(make_auth_client):
    client, store = make_auth_client()

    response = client.post(
        "/auth/register", json={"email": "new@example.com", "password": "password123"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert "password" not in body
    assert "password_hash" not in body
    assert "new@example.com" in store


def test_register_rejects_a_duplicate_email(make_auth_client):
    client, _ = make_auth_client(
        seed_users={
            "taken@example.com": {
                "id": 1,
                "email": "taken@example.com",
                "password_hash": hash_password("whatever123"),
                "created_at": "2026-08-01T00:00:00+00:00",
            }
        }
    )

    response = client.post(
        "/auth/register", json={"email": "taken@example.com", "password": "password123"}
    )

    assert response.status_code == 409


def test_login_sets_an_httponly_cookie_and_returns_the_user(make_auth_client):
    client, _ = make_auth_client()
    client.post("/auth/register", json={"email": "user@example.com", "password": "password123"})

    response = client.post(
        "/auth/login", json={"email": "user@example.com", "password": "password123"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert "access_token" in response.cookies


def test_login_rejects_a_wrong_password(make_auth_client):
    client, _ = make_auth_client()
    client.post("/auth/register", json={"email": "user@example.com", "password": "password123"})

    response = client.post(
        "/auth/login", json={"email": "user@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert "access_token" not in response.cookies


def test_login_rejects_an_unknown_email(make_auth_client):
    client, _ = make_auth_client()

    response = client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": "password123"}
    )

    assert response.status_code == 401


def test_me_requires_a_session_cookie(make_auth_client):
    client, _ = make_auth_client()

    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_returns_the_logged_in_user_via_the_session_cookie(make_auth_client):
    client, _ = make_auth_client()
    client.post("/auth/register", json={"email": "user@example.com", "password": "password123"})
    client.post("/auth/login", json={"email": "user@example.com", "password": "password123"})

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_logout_clears_the_session_cookie(make_auth_client):
    client, _ = make_auth_client()
    client.post("/auth/register", json={"email": "user@example.com", "password": "password123"})
    client.post("/auth/login", json={"email": "user@example.com", "password": "password123"})

    client.post("/auth/logout")
    response = client.get("/auth/me")

    assert response.status_code == 401
