"""Fire-and-forget façade over ActivityStore — never raises to the caller."""
from typing import Optional

from .activity_store import ActivityStore
from ..core.logging_config import get_logger

try:
    from ..security.sensitive_data_redactor import redact_dict
except Exception:  # pragma: no cover - defensive import
    redact_dict = None

logger = get_logger(__name__)


class ActivityLogger:
    """Wraps ActivityStore so a logging failure never breaks the primary request."""

    def __init__(self, store: ActivityStore):
        self._store = store

    def log(
        self,
        user_id: Optional[str],
        event_type: str,
        description: str,
        metadata: Optional[dict] = None,
    ) -> None:
        if not user_id:
            return
        try:
            safe_metadata = metadata
            if metadata and redact_dict is not None:
                try:
                    safe_metadata = redact_dict(metadata)
                except Exception:
                    safe_metadata = metadata
            self._store.log(user_id, event_type, description[:2000], safe_metadata)
        except Exception as e:
            logger.warning(f"ActivityLogger failed to record '{event_type}' for user {user_id}: {e}")
