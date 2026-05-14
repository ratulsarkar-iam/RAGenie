from typing import List, Any
from .context_analyzer import UserContext
from .content_generator import Briefing, Nudge
from ..core.logging_config import get_logger

logger = get_logger(__name__)


def send_push_notification(notification: Any) -> None:
    """Send a push notification via macOS osascript."""
    content = getattr(notification, "content", "") or getattr(notification, "message", "")
    try:
        import subprocess
        msg = str(content)[:100].replace('"', "'")
        subprocess.run(
            ["osascript", "-e", f'display notification "{msg}" with title "RAGenie Assistant"'],
            check=False, capture_output=True
        )
        logger.info(f"[PUSH] Notification sent: {msg[:60]}")
    except Exception as e:
        logger.warning(f"Push notification failed (non-critical): {e}")


def send_email(notification: Any) -> None:
    """Stub email delivery — logs for now."""
    content = getattr(notification, "content", "") or getattr(notification, "message", "")
    logger.info(f"[EMAIL] Would send: {str(content)[:80]}")


def update_dashboard(notification: Any) -> None:
    """Update the dashboard with the notification content."""
    content = getattr(notification, "content", "") or getattr(notification, "message", "")
    logger.info(f"[DASHBOARD] {str(content)[:120]}")


class NotificationService:
    """Delivers notifications through available channels."""

    def send_push_notification(self, notification: Any) -> None:
        """Instance proxy to module-level send_push_notification."""
        send_push_notification(notification)

    def send_email(self, notification: Any) -> None:
        send_email(notification)

    def update_dashboard(self, notification: Any) -> None:
        update_dashboard(notification)

    def is_appropriate_time(self, notification: Any, context: UserContext) -> bool:
        tc = context.time_context
        if tc is None:
            return True
        if tc.is_quiet_hours:
            return getattr(notification, "priority", "medium") == "urgent"
        if tc.in_meeting:
            return getattr(notification, "priority", "medium") in ("urgent", "high")
        return True

    async def deliver(self, notification: Any) -> None:
        channels = getattr(notification, "channels", ["dashboard"])

        for channel in channels:
            if channel == "notification":
                send_push_notification(notification)
            elif channel == "email":
                send_email(notification)
            elif channel == "dashboard":
                update_dashboard(notification)
