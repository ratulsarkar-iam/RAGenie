from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum


class TaskType(str, Enum):
    REMINDER = "reminder"
    CALENDAR = "calendar"
    NOTE = "note"
    EMAIL = "email"
    UNKNOWN = "unknown"


@dataclass
class Task:
    action_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    priority: str = "medium"
    raw_request: str = ""


class TaskParser:
    """Parses natural language task requests into structured Task objects."""

    def __init__(self, llm_wrapper=None):
        self.llm = llm_wrapper

    async def parse_request(self, request: str, context: Dict[str, Any]) -> Task:
        if self.llm:
            return await self._parse_with_llm(request, context)
        return self._parse_with_rules(request)

    async def _parse_with_llm(self, request: str, context: Dict[str, Any]) -> Task:
        import json
        prompt = (
            f"Parse this task request into JSON with keys: action_type, parameters, priority.\n"
            f"Context: {context}\n"
            f"Request: {request}\n"
            f"Return only valid JSON."
        )
        try:
            raw = await self.llm.generate(prompt)
            data = json.loads(raw)
            return Task(
                action_type=data.get("action_type", "unknown"),
                parameters=data.get("parameters", {}),
                priority=data.get("priority", "medium"),
                raw_request=request
            )
        except Exception:
            return self._parse_with_rules(request)

    def _parse_with_rules(self, request: str) -> Task:
        lower = request.lower()
        if any(w in lower for w in ["remind", "reminder"]):
            return Task(action_type="reminder", parameters={"message": request}, priority="medium")
        if any(w in lower for w in ["calendar", "meeting", "event", "schedule"]):
            return Task(action_type="calendar", parameters={"title": request}, priority="high")
        if any(w in lower for w in ["note", "write down", "save"]):
            return Task(action_type="note", parameters={"content": request}, priority="low")
        return Task(action_type="unknown", parameters={}, priority="low", raw_request=request)
