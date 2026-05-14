"""
Tests for Authentication System
Covers: UserStore (PBKDF2 hashing, CRUD), JWTManager (create/decode tokens),
        auth API endpoints via FastAPI TestClient
Spec: openspec/changes/security-hardening/specs/authentication/spec.md
"""
import os
import tempfile
import time
import pytest
from starlette.testclient import TestClient
from fastapi import FastAPI


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "users.db")


@pytest.fixture
def user_store(tmp_db):
    from src.auth.user_store import UserStore
    return UserStore(db_path=tmp_db)


@pytest.fixture
def auth_client(tmp_db):
    """Minimal FastAPI app with only auth routes, backed by a temp DB."""
    from src.api.auth_routes import router as auth_router, init_auth_routes
    from src.auth.user_store import UserStore
    from src.auth.dependencies import set_user_store

    store = UserStore(db_path=tmp_db)
    set_user_store(store)
    init_auth_routes(store)

    app = FastAPI()
    app.include_router(auth_router)
    return TestClient(app)


# ── UserStore ─────────────────────────────────────────────────────────────────

class TestUserStore:
    """Tests for UserStore CRUD and password security."""

    def test_db_table_created(self, user_store):
        import sqlite3
        with sqlite3.connect(user_store.db_path) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone()
        assert row is not None

    def test_create_user_returns_user_object(self, user_store):
        from src.auth.models import User
        u = user_store.create_user("alice@example.com", "password123")
        assert isinstance(u, User)
        assert u.email == "alice@example.com"
        assert u.role == "user"
        assert u.is_active is True

    def test_password_not_stored_as_plaintext(self, user_store):
        user_store.create_user("bob@example.com", "mysecret")
        row = user_store.get_by_email("bob@example.com")
        assert "mysecret" not in row["hashed_password"]

    def test_password_hash_uses_pbkdf2_prefix(self, user_store):
        user_store.create_user("carol@example.com", "test1234")
        row = user_store.get_by_email("carol@example.com")
        assert row["hashed_password"].startswith("pbkdf2:")

    def test_verify_correct_password(self, user_store):
        user_store.create_user("dave@example.com", "correct_password")
        row = user_store.get_by_email("dave@example.com")
        assert user_store.verify_password("correct_password", row["hashed_password"]) is True

    def test_verify_wrong_password(self, user_store):
        user_store.create_user("eve@example.com", "correct_password")
        row = user_store.get_by_email("eve@example.com")
        assert user_store.verify_password("wrong_password", row["hashed_password"]) is False

    def test_verify_empty_password_fails(self, user_store):
        user_store.create_user("frank@example.com", "somepassword")
        row = user_store.get_by_email("frank@example.com")
        assert user_store.verify_password("", row["hashed_password"]) is False

    def test_same_password_produces_different_hashes(self, user_store):
        """Salt ensures two users with the same password get different hashes."""
        user_store.create_user("g@example.com", "samepass")
        user_store.create_user("h@example.com", "samepass")
        row_g = user_store.get_by_email("g@example.com")
        row_h = user_store.get_by_email("h@example.com")
        assert row_g["hashed_password"] != row_h["hashed_password"]

    def test_get_by_email_case_insensitive(self, user_store):
        user_store.create_user("Ivan@Example.COM", "pass1234")
        row = user_store.get_by_email("ivan@example.com")
        assert row is not None

    def test_get_by_email_not_found_returns_none(self, user_store):
        assert user_store.get_by_email("nonexistent@example.com") is None

    def test_get_by_id(self, user_store):
        u = user_store.create_user("jane@example.com", "pass1234")
        row = user_store.get_by_id(u.id)
        assert row["email"] == "jane@example.com"

    def test_get_by_id_not_found_returns_none(self, user_store):
        assert user_store.get_by_id("00000000-0000-0000-0000-000000000000") is None

    def test_email_exists_true(self, user_store):
        user_store.create_user("kate@example.com", "pass1234")
        assert user_store.email_exists("kate@example.com") is True

    def test_email_exists_false(self, user_store):
        assert user_store.email_exists("nobody@example.com") is False

    def test_count_users_increments(self, user_store):
        assert user_store.count_users() == 0
        user_store.create_user("l@example.com", "pass1234")
        assert user_store.count_users() == 1
        user_store.create_user("m@example.com", "pass1234")
        assert user_store.count_users() == 2

    def test_update_last_login(self, user_store):
        u = user_store.create_user("n@example.com", "pass1234")
        user_store.update_last_login(u.id)
        row = user_store.get_by_id(u.id)
        assert row["last_login"] is not None

    def test_update_password(self, user_store):
        u = user_store.create_user("o@example.com", "oldpass1")
        user_store.update_password(u.id, "newpass1")
        row = user_store.get_by_id(u.id)
        assert user_store.verify_password("newpass1", row["hashed_password"]) is True
        assert user_store.verify_password("oldpass1", row["hashed_password"]) is False

    def test_duplicate_email_raises(self, user_store):
        user_store.create_user("p@example.com", "pass1234")
        with pytest.raises(Exception):
            user_store.create_user("p@example.com", "different")


# ── JWTManager ────────────────────────────────────────────────────────────────

class TestJWTManager:
    """Tests for create_access_token, create_refresh_token, decode_token."""

    def test_access_token_is_string(self):
        from src.auth.jwt_manager import create_access_token
        token = create_access_token({"sub": "user-1", "role": "user"})
        assert isinstance(token, str)
        assert len(token) > 20

    def test_decode_valid_access_token(self):
        from src.auth.jwt_manager import create_access_token, decode_token
        token = create_access_token({"sub": "user-42", "role": "admin"})
        payload = decode_token(token)
        assert payload["sub"] == "user-42"
        assert payload["role"] == "admin"

    def test_access_token_has_exp_claim(self):
        from src.auth.jwt_manager import create_access_token, decode_token
        token = create_access_token({"sub": "u"})
        payload = decode_token(token)
        assert "exp" in payload

    def test_expired_token_raises_value_error(self):
        from src.auth.jwt_manager import create_access_token, decode_token
        token = create_access_token({"sub": "u"}, expires_minutes=-1)
        with pytest.raises(ValueError, match="expired"):
            decode_token(token)

    def test_tampered_token_raises_value_error(self):
        from src.auth.jwt_manager import create_access_token, decode_token
        token = create_access_token({"sub": "u"})
        # Flip the last few characters to tamper with the signature
        tampered = token[:-4] + "XXXX"
        with pytest.raises(ValueError):
            decode_token(tampered)

    def test_garbage_token_raises_value_error(self):
        from src.auth.jwt_manager import decode_token
        with pytest.raises(ValueError):
            decode_token("not.a.jwt")

    def test_refresh_token_has_type_refresh(self):
        from src.auth.jwt_manager import create_refresh_token, decode_token
        token = create_refresh_token("user-99")
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user-99"

    def test_refresh_token_different_from_access_token(self):
        from src.auth.jwt_manager import create_access_token, create_refresh_token
        access = create_access_token({"sub": "u"})
        refresh = create_refresh_token("u")
        assert access != refresh

    def test_tokens_with_different_secrets_are_incompatible(self):
        """Changing SECRET_KEY env var invalidates previously issued tokens."""
        import os
        from src.auth import jwt_manager as jm
        original_secret = jm._SECRET
        token = jm.create_access_token({"sub": "u"})
        # Temporarily change the module-level secret
        jm._SECRET = "completely-different-secret"
        try:
            with pytest.raises(ValueError):
                jm.decode_token(token)
        finally:
            jm._SECRET = original_secret


# ── Auth API Endpoints ────────────────────────────────────────────────────────

class TestAuthEndpoints:
    """Integration tests for /api/auth/* endpoints via TestClient."""

    def test_register_first_user_becomes_admin(self, auth_client):
        r = auth_client.post("/api/auth/register", json={
            "email": "admin@test.com", "password": "adminpass"
        })
        assert r.status_code == 201
        assert r.json()["role"] == "admin"

    def test_register_second_user_is_regular(self, auth_client):
        auth_client.post("/api/auth/register", json={
            "email": "first@test.com", "password": "password1"
        })
        r = auth_client.post("/api/auth/register", json={
            "email": "second@test.com", "password": "password2"
        })
        assert r.status_code == 201
        assert r.json()["role"] == "user"

    def test_register_duplicate_email_returns_409(self, auth_client):
        auth_client.post("/api/auth/register", json={
            "email": "dup@test.com", "password": "password1"
        })
        r = auth_client.post("/api/auth/register", json={
            "email": "dup@test.com", "password": "password2"
        })
        assert r.status_code == 409

    def test_register_short_password_rejected(self, auth_client):
        r = auth_client.post("/api/auth/register", json={
            "email": "short@test.com", "password": "abc"
        })
        assert r.status_code == 422

    def test_login_returns_tokens(self, auth_client):
        auth_client.post("/api/auth/register", json={
            "email": "user@test.com", "password": "mypassword"
        })
        r = auth_client.post("/api/auth/login", json={
            "email": "user@test.com", "password": "mypassword"
        })
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self, auth_client):
        auth_client.post("/api/auth/register", json={
            "email": "user2@test.com", "password": "correctpass"
        })
        r = auth_client.post("/api/auth/login", json={
            "email": "user2@test.com", "password": "wrongpass"
        })
        assert r.status_code == 401

    def test_login_unknown_email_returns_401(self, auth_client):
        r = auth_client.post("/api/auth/login", json={
            "email": "nobody@test.com", "password": "anypassword"
        })
        assert r.status_code == 401

    def test_me_without_token_returns_401(self, auth_client):
        r = auth_client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_with_valid_token_returns_user(self, auth_client):
        auth_client.post("/api/auth/register", json={
            "email": "me@test.com", "password": "password1"
        })
        login = auth_client.post("/api/auth/login", json={
            "email": "me@test.com", "password": "password1"
        })
        token = login.json()["access_token"]
        r = auth_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        assert r.json()["email"] == "me@test.com"

    def test_me_with_expired_token_returns_401(self, auth_client):
        from src.auth.jwt_manager import create_access_token
        expired_token = create_access_token({"sub": "fake-id", "role": "user"}, expires_minutes=-1)
        r = auth_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        assert r.status_code == 401

    def test_me_with_refresh_token_returns_401(self, auth_client):
        """A refresh token must not grant access to protected endpoints."""
        auth_client.post("/api/auth/register", json={
            "email": "refresh@test.com", "password": "password1"
        })
        login = auth_client.post("/api/auth/login", json={
            "email": "refresh@test.com", "password": "password1"
        })
        refresh_token = login.json()["refresh_token"]
        r = auth_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )
        assert r.status_code == 401

    def test_token_refresh_returns_new_access_token(self, auth_client):
        auth_client.post("/api/auth/register", json={
            "email": "rf@test.com", "password": "password1"
        })
        login = auth_client.post("/api/auth/login", json={
            "email": "rf@test.com", "password": "password1"
        })
        refresh_token = login.json()["refresh_token"]
        r = auth_client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_token_refresh_with_access_token_fails(self, auth_client):
        """An access token must not be accepted as a refresh token."""
        auth_client.post("/api/auth/register", json={
            "email": "bad@test.com", "password": "password1"
        })
        login = auth_client.post("/api/auth/login", json={
            "email": "bad@test.com", "password": "password1"
        })
        access_token = login.json()["access_token"]
        r = auth_client.post("/api/auth/refresh", json={"refresh_token": access_token})
        assert r.status_code == 401

    def test_change_password(self, auth_client):
        auth_client.post("/api/auth/register", json={
            "email": "cp@test.com", "password": "oldpassword"
        })
        login = auth_client.post("/api/auth/login", json={
            "email": "cp@test.com", "password": "oldpassword"
        })
        token = login.json()["access_token"]
        r = auth_client.post(
            "/api/auth/change-password",
            json={"current_password": "oldpassword", "new_password": "newpassword"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        # Old password should no longer work
        r2 = auth_client.post("/api/auth/login", json={
            "email": "cp@test.com", "password": "oldpassword"
        })
        assert r2.status_code == 401
        # New password should work
        r3 = auth_client.post("/api/auth/login", json={
            "email": "cp@test.com", "password": "newpassword"
        })
        assert r3.status_code == 200

    def test_list_users_requires_admin(self, auth_client):
        # Register two users — first is admin
        auth_client.post("/api/auth/register", json={
            "email": "admin2@test.com", "password": "adminpass"
        })
        auth_client.post("/api/auth/register", json={
            "email": "regular@test.com", "password": "userpass1"
        })
        # Login as regular user
        login = auth_client.post("/api/auth/login", json={
            "email": "regular@test.com", "password": "userpass1"
        })
        token = login.json()["access_token"]
        r = auth_client.get(
            "/api/auth/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 403

    def test_list_users_admin_succeeds(self, auth_client):
        auth_client.post("/api/auth/register", json={
            "email": "admin3@test.com", "password": "adminpass"
        })
        login = auth_client.post("/api/auth/login", json={
            "email": "admin3@test.com", "password": "adminpass"
        })
        token = login.json()["access_token"]
        r = auth_client.get(
            "/api/auth/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1
