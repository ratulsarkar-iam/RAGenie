import re
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from .mcp_manager import MCPManager
from .action_registry import ActionRegistry
from ..core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TaskResult:
    success: bool
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class TaskEngine:
    """Detects and executes tasks from natural language requests."""

    REMINDER_PATTERNS = [
        r"remind\s+me",
        r"set\s+a?\s*\w*\s*reminder",
        r"create\s+a?\s*\w*\s*reminder",
        r"add\s+a?\s*\w*\s*reminder",
        r"don'?t\s+let\s+me\s+forget",
        r"alert\s+me"
    ]

    CALENDAR_PATTERNS = [
        r"schedule\s+a?\s*(meeting|event|call|appointment)",
        r"add\s+to\s+(calendar|schedule)",
        r"book\s+(a\s+)?(meeting|slot|time)",
        r"create\s+(a\s+)?(meeting|event|appointment)"
    ]

    NOTE_PATTERNS = [
        r"take\s+a?\s*note",
        r"save\s+(this|note)",
        r"write\s+(this\s+)?down",
        r"create\s+a?\s*note"
    ]

    def __init__(self, mcp_manager: MCPManager, action_registry: Optional[ActionRegistry] = None):
        self.mcp_manager = mcp_manager
        self.action_registry = action_registry or ActionRegistry()

    def _detect_task_type(self, request: str) -> Optional[str]:
        lower = request.lower()
        for pattern in self.REMINDER_PATTERNS:
            if re.search(pattern, lower):
                return "reminder"
        for pattern in self.CALENDAR_PATTERNS:
            if re.search(pattern, lower):
                return "calendar"
        for pattern in self.NOTE_PATTERNS:
            if re.search(pattern, lower):
                return "note"
        return None

    def _extract_title(self, request: str) -> str:
        stop_words = ["remind me to", "set a reminder to", "schedule a meeting about",
                      "create an event for", "add to calendar", "take a note about"]
        title = request
        for sw in stop_words:
            title = re.sub(sw, "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\b(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                       "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\bat\s+\d+\s*(am|pm|:\d+)?\b", "", title, flags=re.IGNORECASE).strip()
        return title.strip(" .,") or request[:50]

    async def execute_task(self, request: str, context: Optional[Dict] = None) -> TaskResult:
        task_type = self._detect_task_type(request)

        if task_type is None:
            return TaskResult(success=False, summary="Could not understand the task request")

        title = self._extract_title(request)

        if task_type == "reminder":
            return await self._create_reminder(title, request)
        elif task_type == "calendar":
            return await self._create_calendar_event(title, request)
        elif task_type == "note":
            return await self._create_note(title, request)

        return TaskResult(success=False, summary="Unsupported task type")

    async def _create_reminder(self, title: str, original: str) -> TaskResult:
        try:
            result = await self.mcp_manager.execute_action("reminders", "create_reminder", {
                "title": title,
                "notes": original,
                "priority": 1
            })
            return TaskResult(
                success=True,
                summary=f"Reminder created: '{title}'",
                details=result
            )
        except Exception as e:
            logger.error(f"Reminder creation failed: {e}")
            return TaskResult(success=False, summary=f"Failed to create reminder: {e}")

    async def _create_calendar_event(self, title: str, original: str) -> TaskResult:
        try:
            result = await self.mcp_manager.execute_action("calendar", "create_event", {
                "title": title,
                "notes": original,
                "duration_minutes": 60
            })
            return TaskResult(
                success=True,
                summary=f"Calendar event created: '{title}'",
                details=result
            )
        except Exception as e:
            logger.error(f"Calendar event creation failed: {e}")
            return TaskResult(success=False, summary=f"Failed to create calendar event: {e}")

    async def _create_note(self, title: str, original: str) -> TaskResult:
        import os
        from pathlib import Path
        notes_dir = Path("data/notes")
        notes_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w\s-]", "", title)[:50].strip()
        filepath = notes_dir / f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        try:
            filepath.write_text(f"# {title}\n\nCreated: {datetime.utcnow()}\n\n{original}")
            return TaskResult(
                success=True,
                summary=f"Note saved: '{filepath.name}'",
                details={"path": str(filepath)}
            )
        except Exception as e:
            logger.error(f"Note creation failed: {e}")
            return TaskResult(success=False, summary=f"Failed to create note: {e}")
