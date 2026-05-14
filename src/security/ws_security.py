"""WebSocket message validation and per-connection rate limiting."""
import time
from collections import defaultdict
from typing import Dict, List, Tuple

_MAX_MESSAGE_LENGTH = 10_000
_MAX_MESSAGES_PER_MINUTE = 30
_WINDOW_SECONDS = 60.0

_message_times: Dict[str, List[float]] = defaultdict(list)


def validate_ws_message(data: dict) -> Tuple[bool, str]:
    """Validate an incoming WebSocket message dict.

    Returns:
        (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Message must be a JSON object"

    message = data.get("message", "")
    if not isinstance(message, str):
        return False, "'message' field must be a string"

    if not message.strip():
        return False, "Empty message"

    if len(message) > _MAX_MESSAGE_LENGTH:
        return False, (
            f"Message too long ({len(message):,} chars, "
            f"max {_MAX_MESSAGE_LENGTH:,})"
        )

    conv_id = data.get("conversation_id", "default")
    if not isinstance(conv_id, str) or len(conv_id) > 128:
        return False, "Invalid conversation_id"

    use_reasoning = data.get("use_reasoning", False)
    if not isinstance(use_reasoning, bool):
        return False, "'use_reasoning' must be a boolean"

    return True, ""


def check_ws_rate_limit(client_id: str) -> Tuple[bool, int]:
    """Sliding-window rate limit for a WebSocket client.

    Returns:
        (is_allowed, retry_after_seconds)
    """
    now = time.monotonic()
    _message_times[client_id] = [
        ts for ts in _message_times[client_id]
        if now - ts < _WINDOW_SECONDS
    ]

    if len(_message_times[client_id]) >= _MAX_MESSAGES_PER_MINUTE:
        oldest = min(_message_times[client_id])
        retry_after = int(_WINDOW_SECONDS - (now - oldest)) + 1
        return False, retry_after

    _message_times[client_id].append(now)
    return True, 0


def cleanup_client(client_id: str) -> None:
    """Remove tracking state for a disconnected client."""
    _message_times.pop(client_id, None)
