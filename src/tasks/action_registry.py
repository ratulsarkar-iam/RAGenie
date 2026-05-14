from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from ..core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Action:
    name: str
    description: str
    mcp_client: str
    mcp_action: str
    required_params: List[str]


class ActionRegistry:
    """Registry of available actions and their handlers."""

    def __init__(self):
        self.actions: Dict[str, Action] = {}
        self._register_builtin_actions()

    def _register_builtin_actions(self):
        self.register_action(Action(
            name="create_reminder",
            description="Create a reminder in macOS Reminders",
            mcp_client="reminders",
            mcp_action="create_reminder",
            required_params=["title"]
        ))
        self.register_action(Action(
            name="create_calendar_event",
            description="Create an event in macOS Calendar",
            mcp_client="calendar",
            mcp_action="create_event",
            required_params=["title", "start_date"]
        ))
        self.register_action(Action(
            name="create_note",
            description="Create a note file",
            mcp_client="filesystem",
            mcp_action="write_file",
            required_params=["path", "content"]
        ))
        self.register_action(Action(
            name="list_files",
            description="List files in a directory",
            mcp_client="filesystem",
            mcp_action="list_directory",
            required_params=["path"]
        ))

    def register_action(self, action: Action) -> None:
        self.actions[action.name] = action

    def get_action(self, name: str) -> Optional[Action]:
        return self.actions.get(name)

    def list_actions(self) -> List[Action]:
        return list(self.actions.values())

    def get_actions_description(self) -> str:
        lines = []
        for action in self.actions.values():
            lines.append(f"- {action.name}: {action.description}")
        return "\n".join(lines)
