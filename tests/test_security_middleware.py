"""
Tests for Security Middleware (Integration)
Covers: SecurityHeadersMiddleware (OWASP headers),
        RateLimitMiddleware (rate headers, 429 enforcement),
        CORS origins from config,
        file upload endpoint security (extension + magic bytes via validate_upload)
Spec: openspec/changes/security-hardening/specs/websocket-security/spec.md
      openspec/changes/security-hardening/specs/file-upload-security/spec.md
"""
import io
import pytest
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from starlette.testclient import TestClient

from src.security.security_headers_middleware import SecurityHeadersMiddleware
from src.security.rate_limit_middleware import RateLimitMiddleware
import src.security.rate_limit_middleware as rl_mod


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def security_app():
    """Minimal FastAPI app with both security middlewares + CORS."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, enabled=True)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/ping")
    def ping():
        return {"status": "ok"}

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    return app


@pytest.fixture
def client(security_app):
    return TestClient(security_app, raise_server_exceptions=True)


@pytest.fixture
def unique_ip(request):
    """Return a unique IP per test to avoid shared rate-limit state."""
    return f"10.0.{request.node.nodeid.__hash__() % 255}.{id(request) % 255}"


# ── SecurityHeadersMiddleware ─────────────────────────────────────────────────

class TestSecurityHeaders:
    """Verify OWASP-recommended headers are present on every response."""

    def test_x_content_type_options_nosniff(self, client):
        r = client.get("/ping")
        assert r.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options_deny(self, client):
        r = client.get("/ping")
        val = r.headers.get("x-frame-options", "").upper()
        assert val in ("DENY", "SAMEORIGIN")

    def test_content_security_policy_present(self, client):
        r = client.get("/ping")
        assert "content-security-policy" in r.headers

    def test_referrer_policy_present(self, client):
        r = client.get("/ping")
        assert "referrer-policy" in r.headers

    def test_permissions_policy_present(self, client):
        r = client.get("/ping")
        assert "permissions-policy" in r.headers

    def test_headers_on_404_response(self, client):
        r = client.get("/nonexistent-route")
        assert "x-content-type-options" in r.headers

    def test_headers_on_post_response(self, client, security_app):
        @security_app.post("/data")
        def data():
            return {}
        r = client.post("/data")
        assert "x-content-type-options" in r.headers


# ── RateLimitMiddleware ───────────────────────────────────────────────────────

class TestRateLimitMiddleware:
    """Verify rate-limit headers and 429 enforcement."""

    def test_rate_limit_headers_on_success(self, client, unique_ip):
        r = client.get("/ping", headers={"X-Forwarded-For": unique_ip})
        assert "x-ratelimit-limit" in r.headers
        assert "x-ratelimit-remaining" in r.headers

    def test_remaining_decrements_on_each_request(self, client, unique_ip):
        r1 = client.get("/ping", headers={"X-Forwarded-For": unique_ip})
        r2 = client.get("/ping", headers={"X-Forwarded-For": unique_ip})
        rem1 = int(r1.headers["x-ratelimit-remaining"])
        rem2 = int(r2.headers["x-ratelimit-remaining"])
        assert rem2 == rem1 - 1

    def test_skip_paths_not_rate_limited(self, client):
        """Health / docs endpoints must bypass rate limiting."""
        r = client.get("/health")
        assert r.status_code == 200
        assert "x-ratelimit-limit" not in r.headers

    def test_rate_limit_triggers_429(self, unique_ip):
        """With a very low limit, the middleware must return 429."""
        original = dict(rl_mod._TIERS)
        rl_mod._TIERS["default"] = (3, 60)

        try:
            app = FastAPI()
            app.add_middleware(RateLimitMiddleware, enabled=True)

            @app.get("/t")
            def t():
                return {}

            c = TestClient(app, raise_server_exceptions=False)
            ip = unique_ip

            r1 = c.get("/t", headers={"X-Forwarded-For": ip})
            r2 = c.get("/t", headers={"X-Forwarded-For": ip})
            r3 = c.get("/t", headers={"X-Forwarded-For": ip})
            r4 = c.get("/t", headers={"X-Forwarded-For": ip})

            assert r1.status_code == 200
            assert r2.status_code == 200
            assert r3.status_code == 200
            assert r4.status_code == 429
        finally:
            rl_mod._TIERS.clear()
            rl_mod._TIERS.update(original)

    def test_429_includes_retry_after(self, unique_ip):
        original = dict(rl_mod._TIERS)
        rl_mod._TIERS["default"] = (2, 60)

        try:
            app = FastAPI()
            app.add_middleware(RateLimitMiddleware, enabled=True)

            @app.get("/t")
            def t():
                return {}

            c = TestClient(app, raise_server_exceptions=False)
            ip = unique_ip
            c.get("/t", headers={"X-Forwarded-For": ip})
            c.get("/t", headers={"X-Forwarded-For": ip})
            r = c.get("/t", headers={"X-Forwarded-For": ip})

            assert r.status_code == 429
            assert "retry-after" in r.headers
            assert int(r.headers["retry-after"]) > 0
        finally:
            rl_mod._TIERS.clear()
            rl_mod._TIERS.update(original)

    def test_different_ips_have_independent_limits(self, unique_ip):
        original = dict(rl_mod._TIERS)
        rl_mod._TIERS["default"] = (2, 60)

        try:
            app = FastAPI()
            app.add_middleware(RateLimitMiddleware, enabled=True)

            @app.get("/t")
            def t():
                return {}

            c = TestClient(app, raise_server_exceptions=False)
            # Exhaust ip_a
            c.get("/t", headers={"X-Forwarded-For": f"{unique_ip}.A"})
            c.get("/t", headers={"X-Forwarded-For": f"{unique_ip}.A"})
            limited = c.get("/t", headers={"X-Forwarded-For": f"{unique_ip}.A"})
            # ip_b should still be allowed
            fresh = c.get("/t", headers={"X-Forwarded-For": f"{unique_ip}.B"})

            assert limited.status_code == 429
            assert fresh.status_code == 200
        finally:
            rl_mod._TIERS.clear()
            rl_mod._TIERS.update(original)

    def test_middleware_disabled_skips_limiting(self, unique_ip):
        original = dict(rl_mod._TIERS)
        rl_mod._TIERS["default"] = (1, 60)

        try:
            app = FastAPI()
            app.add_middleware(RateLimitMiddleware, enabled=False)

            @app.get("/t")
            def t():
                return {}

            c = TestClient(app, raise_server_exceptions=False)
            for _ in range(5):
                r = c.get("/t", headers={"X-Forwarded-For": unique_ip})
                assert r.status_code == 200
        finally:
            rl_mod._TIERS.clear()
            rl_mod._TIERS.update(original)


# ── CORS ──────────────────────────────────────────────────────────────────────

class TestCORS:
    """Verify CORS headers for allowed and disallowed origins."""

    def test_allowed_origin_gets_cors_header(self, client):
        r = client.get("/ping", headers={"Origin": "http://localhost:3000"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_disallowed_origin_no_cors_header(self, client):
        r = client.get("/ping", headers={"Origin": "http://evil.com"})
        assert r.headers.get("access-control-allow-origin") != "http://evil.com"

    def test_preflight_returns_200(self, client):
        r = client.options(
            "/ping",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code in (200, 204)


# ── Upload endpoint validation (via validate_upload directly) ─────────────────

class TestUploadValidation:
    """
    The actual /upload and /chat-upload endpoints require the full RAG stack,
    so we verify the security gate (validate_upload) that both endpoints call.
    These tests confirm the gate logic is correct end-to-end.
    """

    def test_pdf_valid_accepted(self):
        from src.security.file_validator import validate_upload
        ok, _ = validate_upload("doc.pdf", b"%PDF-1.4 " + b"\x00" * 50)
        assert ok is True

    def test_pdf_fake_magic_rejected(self):
        from src.security.file_validator import validate_upload
        ok, err = validate_upload("fake.pdf", b"PK\x03\x04" + b"\x00" * 50)
        assert ok is False

    def test_pe_disguised_as_txt_rejected(self):
        from src.security.file_validator import validate_upload
        ok, err = validate_upload("notes.txt", b"MZ\x90\x00" + b"\x00" * 100)
        assert ok is False
        assert "executable" in err.lower()

    def test_elf_disguised_as_csv_rejected(self):
        from src.security.file_validator import validate_upload
        ok, err = validate_upload("data.csv", b"\x7fELF" + b"\x00" * 100)
        assert ok is False

    def test_extension_not_in_allowlist_rejected(self):
        from src.security.file_validator import validate_upload
        ok, err = validate_upload("code.php", b"<?php echo 'hi'; ?>")
        assert ok is False
        assert "not allowed" in err.lower()

    def test_empty_file_rejected(self):
        from src.security.file_validator import validate_upload
        ok, err = validate_upload("empty.txt", b"")
        assert ok is False
        assert "empty" in err.lower()

    def test_path_traversal_filename_no_valid_extension(self):
        from src.security.file_validator import validate_upload
        ok, err = validate_upload("../../etc/passwd", b"root:x:0:0")
        assert ok is False
