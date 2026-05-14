from typing import Optional, Dict, Any
from datetime import datetime, timezone
from .memory_store import MemoryStore
from .models import Memory, MemoryType
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """Orchestrates memory operations and provides context to LLM."""

    def __init__(self, memory_store: MemoryStore):
        self.store = memory_store

    def add_context(self, content: str, memory_type: MemoryType, metadata: Optional[Dict[str, Any]] = None) -> str:
        memory = Memory(
            type=memory_type,
            content=content,
            metadata=metadata or {}
        )
        return self.store.store_memory(memory)

    def get_relevant_context(self, query: str, max_context: int = 2000) -> str:
        memories = self.store.retrieve_memories(query, limit=8)
        if not memories:
            return ""

        context_parts = []
        current_length = 0

        for memory in memories:
            entry = f"[{memory.type.value}] {memory.content}"
            if current_length + len(entry) > max_context:
                break
            context_parts.append(entry)
            current_length += len(entry)

        return "\n".join(context_parts)

    def update_preferences(self, preferences: Dict[str, Any]) -> None:
        existing = self.store.get_profile_value("preferences") or {}
        existing.update(preferences)
        self.store.set_profile_value("preferences", existing)

        for key, value in preferences.items():
            self.add_context(
                f"User prefers: {key} = {value}",
                MemoryType.PREFERENCE,
                {"preference_key": key, "preference_value": str(value)}
            )

    def track_learning(self, topic: str, mastery: float) -> None:
        self.store.set_mastery(topic, mastery)
        self.add_context(
            f"Learning progress in {topic}: {mastery:.2f}",
            MemoryType.LEARNING,
            {"topic": topic, "mastery": mastery}
        )

    def store_conversation(self, user_message: str, assistant_response: str) -> None:
        self.add_context(
            f"User: {user_message}\nAssistant: {assistant_response[:300]}",
            MemoryType.CONVERSATION,
            {"timestamp": datetime.now(timezone.utc).isoformat()}
        )

    def get_user_profile(self) -> Dict[str, Any]:
        return {
            "preferences": self.store.get_profile_value("preferences") or {},
            "learning_goals": self.store.get_profile_value("learning_goals") or [],
            "interaction_style": self.store.get_profile_value("interaction_style") or "balanced"
        }

    def set_learning_goals(self, goals: list) -> None:
        self.store.set_profile_value("learning_goals", goals)
        for goal in goals:
            self.add_context(
                f"Learning goal: {goal}",
                MemoryType.GOAL,
                {"goal": goal}
            )
