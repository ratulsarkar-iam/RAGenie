"""
Tests for WebSocket Security and Sensitive Data Redaction
Covers: ws_security (message validation, rate limiting, cleanup),
        sensitive_data_redactor (PII patterns, dict redaction)
Spec: openspec/changes/security-hardening/specs/websocket-security/spec.md
"""
import pytest
from src.security.ws_security import (
    validate_ws_message,
    check_ws_rate_limit,
    cleanup_client,
    _message_times,
    _MAX_MESSAGE_LENGTH,
    _MAX_MESSAGES_PER_MINUTE,
)
from src.security.sensitive_data_redactor import redact, redact_dict


# ── WebSocket Message Validation ──────────────────────────────────────────────

class TestWsMessageValidation:
    """Tests for validate_ws_message()."""

    def test_valid_message_passes(self):
        data = {"message": "Hello, how are you?"}
        ok, err = validate_ws_message(data)
        assert ok is True
        assert err == ""

    def test_valid_message_with_all_fields(self):
        data = {
            "message": "What is Python?",
            "conversation_id": "conv-123",
            "use_reasoning": False,
            "use_agent": False,
        }
        ok, err = validate_ws_message(data)
        assert ok is True

    def test_empty_message_rejected(self):
        ok, err = validate_ws_message({"message": ""})
        assert ok is False
        assert len(err) > 0

    def test_whitespace_only_message_rejected(self):
        ok, err = validate_ws_message({"message": "   \t\n  "})
        assert ok is False

    def test_message_too_long_rejected(self):
        ok, err = validate_ws_message({"message": "x" * (_MAX_MESSAGE_LENGTH + 1)})
        assert ok is False
        assert "long" in err.lower() or "max" in err.lower()

    def test_message_at_max_length_passes(self):
        ok, _ = validate_ws_message({"message": "a" * _MAX_MESSAGE_LENGTH})
        assert ok is True

    def test_non_string_message_rejected(self):
        ok, err = validate_ws_message({"message": 12345})
        assert ok is False

    def test_null_message_rejected(self):
        ok, err = validate_ws_message({"message": None})
        assert ok is False

    def test_non_dict_input_rejected(self):
        ok, err = validate_ws_message("raw string")  # type: ignore
        assert ok is False
        assert "JSON object" in err or "dict" in err.lower()

    def test_list_input_rejected(self):
        ok, err = validate_ws_message(["msg"])  # type: ignore
        assert ok is False

    def test_invalid_conversation_id_type_rejected(self):
        ok, err = validate_ws_message({"message": "hi", "conversation_id": 123})
        assert ok is False

    def test_conversation_id_too_long_rejected(self):
        ok, err = validate_ws_message({
            "message": "hi",
            "conversation_id": "x" * 129,
        })
        assert ok is False

    def test_conversation_id_max_length_passes(self):
        ok, _ = validate_ws_message({
            "message": "hi",
            "conversation_id": "x" * 128,
        })
        assert ok is True

    def test_use_reasoning_must_be_bool(self):
        ok, err = validate_ws_message({"message": "hi", "use_reasoning": "true"})
        assert ok is False

    def test_use_reasoning_bool_passes(self):
        ok, _ = validate_ws_message({"message": "hi", "use_reasoning": True})
        assert ok is True

    def test_missing_message_key_rejected(self):
        ok, err = validate_ws_message({"conversation_id": "x"})
        assert ok is False


# ── WebSocket Rate Limiting ───────────────────────────────────────────────────

class TestWsRateLimit:
    """Tests for check_ws_rate_limit() and cleanup_client()."""

    @pytest.fixture(autouse=True)
    def isolate_client(self):
        """Use a unique client ID per test and clean up afterwards."""
        self.client_id = f"test-client-{id(self)}"
        yield
        cleanup_client(self.client_id)

    def test_first_message_allowed(self):
        allowed, retry = check_ws_rate_limit(self.client_id)
        assert allowed is True
        assert retry == 0

    def test_multiple_messages_within_limit_allowed(self):
        for _ in range(5):
            allowed, _ = check_ws_rate_limit(self.client_id)
            assert allowed is True

    def test_exceeding_limit_blocks(self):
        # Fill up to the limit
        for _ in range(_MAX_MESSAGES_PER_MINUTE):
            check_ws_rate_limit(self.client_id)
        # Next one should be blocked
        allowed, retry_after = check_ws_rate_limit(self.client_id)
        assert allowed is False
        assert retry_after > 0

    def test_blocked_retry_after_is_positive(self):
        for _ in range(_MAX_MESSAGES_PER_MINUTE):
            check_ws_rate_limit(self.client_id)
        _, retry = check_ws_rate_limit(self.client_id)
        assert retry > 0

    def test_different_clients_are_independent(self):
        client_a = f"{self.client_id}-A"
        client_b = f"{self.client_id}-B"
        try:
            # Fill client_a to limit
            for _ in range(_MAX_MESSAGES_PER_MINUTE):
                check_ws_rate_limit(client_a)
            allowed_a, _ = check_ws_rate_limit(client_a)
            # client_b should still be allowed
            allowed_b, _ = check_ws_rate_limit(client_b)
            assert allowed_a is False
            assert allowed_b is True
        finally:
            cleanup_client(client_a)
            cleanup_client(client_b)

    def test_cleanup_removes_state(self):
        for _ in range(_MAX_MESSAGES_PER_MINUTE):
            check_ws_rate_limit(self.client_id)
        assert self.client_id in _message_times
        cleanup_client(self.client_id)
        assert self.client_id not in _message_times

    def test_cleanup_nonexistent_client_is_safe(self):
        """Cleaning up a client that never sent messages must not raise."""
        cleanup_client("ghost-client-xyz")


# ── Sensitive Data Redactor ───────────────────────────────────────────────────

class TestSensitiveDataRedactor:
    """Tests for redact() and redact_dict()."""

    # ── String redaction ─────────────────────────────────────────────────────

    def test_email_redacted(self):
        result = redact("Contact me at john.doe@example.com for details.")
        assert "john.doe@example.com" not in result
        assert "[EMAIL]" in result

    def test_phone_redacted(self):
        result = redact("Call me at 555-867-5309 anytime.")
        assert "555-867-5309" not in result
        assert "[PHONE]" in result

    def test_jwt_redacted(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = redact(f"Token: {jwt}")
        assert jwt not in result
        assert "[JWT]" in result

    def test_bearer_api_key_redacted(self):
        result = redact("Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz123456")
        assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result
        assert "[API_KEY]" in result

    def test_url_credentials_redacted(self):
        result = redact("Connect to postgres://admin:secret123@db.example.com/mydb")
        assert "secret123" not in result
        assert "[USER]" in result and "[PASS]" in result

    def test_clean_text_unchanged(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert redact(text) == text

    def test_non_string_returned_as_is(self):
        assert redact(42) == 42  # type: ignore
        assert redact(None) is None  # type: ignore

    def test_multiple_emails_all_redacted(self):
        result = redact("Email a@b.com and c@d.com for info.")
        assert "a@b.com" not in result
        assert "c@d.com" not in result
        assert result.count("[EMAIL]") == 2

    # ── Dict redaction ───────────────────────────────────────────────────────

    def test_dict_password_key_redacted(self):
        d = redact_dict({"username": "alice", "password": "supersecret"})
        assert d["password"] == "[REDACTED]"
        assert d["username"] == "alice"

    def test_dict_token_key_redacted(self):
        d = redact_dict({"token": "abc123xyz"})
        assert d["token"] == "[REDACTED]"

    def test_dict_api_key_redacted(self):
        d = redact_dict({"api_key": "my-secret-key"})
        assert d["api_key"] == "[REDACTED]"

    def test_dict_authorization_redacted(self):
        d = redact_dict({"authorization": "Bearer token123"})
        assert d["authorization"] == "[REDACTED]"

    def test_dict_email_value_redacted(self):
        d = redact_dict({"note": "Send to user@example.com"})
        assert "user@example.com" not in d["note"]
        assert "[EMAIL]" in d["note"]

    def test_dict_clean_values_unchanged(self):
        d = redact_dict({"city": "Paris", "country": "France"})
        assert d["city"] == "Paris"
        assert d["country"] == "France"

    def test_nested_dict_redacted(self):
        d = redact_dict({"user": {"email": "x@y.com", "password": "pass"}})
        assert d["user"]["password"] == "[REDACTED]"
        assert "[EMAIL]" in d["user"]["email"]

    def test_list_values_redacted(self):
        d = redact_dict({"emails": ["a@b.com", "plain text", "c@d.com"]})
        for val in d["emails"]:
            assert "@" not in val or "[EMAIL]" in val

    def test_non_string_non_dict_values_preserved(self):
        d = redact_dict({"count": 42, "active": True, "data": None})
        assert d["count"] == 42
        assert d["active"] is True
        assert d["data"] is None
