"""Dedicated audit logger for security events."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from .sensitive_data_redactor import redact_dict


class AuditLogger:
    """Writes structured JSON security events to a dedicated audit log."""

    def __init__(self, log_path: str = "logs/audit.log"):
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger("ragenie.security.audit")
        if not self._logger.handlers:
            handler = RotatingFileHandler(
                log_path, maxBytes=10 * 1024 * 1024, backupCount=5
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)
            self._logger.propagate = False

    def _emit(self, event_type: str, severity: str = "info", **kwargs) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "severity": severity,
            **redact_dict(kwargs),
        }
        self._logger.info(json.dumps(entry))

    def rate_limit_hit(self, ip: str, path: str, tier: str) -> None:
        self._emit("rate_limit_hit", severity="warning", ip=ip, path=path, tier=tier)

    def upload_blocked(self, ip: str, filename: str, reason: str) -> None:
        self._emit("upload_blocked", severity="warning", ip=ip, filename=filename, reason=reason)

    def path_traversal_attempt(self, ip: str, filename: str) -> None:
        self._emit("path_traversal_attempt", severity="critical", ip=ip, filename=filename)

    def ws_rate_limit_hit(self, client_id: str) -> None:
        self._emit("ws_rate_limit_hit", severity="warning", client_id=client_id)

    def ws_invalid_message(self, client_id: str, reason: str) -> None:
        self._emit("ws_invalid_message", severity="info", client_id=client_id, reason=reason)

    def security_event(self, event: str, severity: str = "info", **kwargs) -> None:
        self._emit(event, severity=severity, **kwargs)


_instance: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    global _instance
    if _instance is None:
        _instance = AuditLogger()
    return _instance


def init_audit_logger(log_path: str) -> AuditLogger:
    global _instance
    _instance = AuditLogger(log_path)
    return _instance
