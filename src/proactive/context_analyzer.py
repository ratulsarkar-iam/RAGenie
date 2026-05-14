from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from ..memory.memory_store import MemoryStore
from ..core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TimeContext:
    current_time: datetime = field(default_factory=datetime.utcnow)
    time_of_day: str = "daytime"
    day_of_week: int = 0
    is_weekend: bool = False
    is_work_hours: bool = True
    is_quiet_hours: bool = False
    in_meeting: bool = False


@dataclass
class UserContext:
    time_context: Optional[TimeContext] = None
    task_context: Dict[str, Any] = field(default_factory=dict)
    learning_context: Dict[str, Any] = field(default_factory=dict)
    preference_context: Dict[str, Any] = field(default_factory=dict)


class ContextAnalyzer:
    """Analyzes user context for proactive opportunities."""

    def __init__(self, memory_store: MemoryStore = None, task_engine=None, quiet_start: int = 22, quiet_end: int = 8):
        self.store = memory_store
        self.task_engine = task_engine
        self.quiet_start = quiet_start
        self.quiet_end = quiet_end

    async def get_time_context(self, now: Optional[datetime] = None) -> "TimeContext":
        return self._build_time_context(now)

    def _build_time_context(self, now: Optional[datetime] = None) -> "TimeContext":
        now = now or datetime.now()
        hour = now.hour

        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        is_quiet = hour >= self.quiet_start or hour < self.quiet_end
        is_work = 9 <= hour < 18 and now.weekday() < 5

        return TimeContext(
            current_time=now,
            time_of_day=time_of_day,
            day_of_week=now.weekday(),
            is_weekend=now.weekday() >= 5,
            is_work_hours=is_work,
            is_quiet_hours=is_quiet
        )

    async def get_task_context(self) -> Dict[str, Any]:
        if self.task_engine:
            try:
                # try get_current_tasks first, fallback to get_pending_tasks
                fn = getattr(self.task_engine, 'get_current_tasks', None) or \
                     getattr(self.task_engine, 'get_pending_tasks', None)
                if fn:
                    tasks = fn()
                    if hasattr(tasks, '__await__'):
                        tasks = await tasks
                    deadlines = [t.get("deadline", "") for t in tasks if t.get("deadline")]
                    return {
                        "current_task": tasks[0].get("title", "") if tasks else "",
                        "pending_count": len(tasks),
                        "today_priorities": [t.get("title", "") for t in tasks[:3]],
                        "upcoming_deadlines": deadlines,
                        "pattern": "focused"
                    }
            except Exception:
                pass
        return {"current_task": "", "pending_count": 0, "today_priorities": [], "upcoming_deadlines": []}

    async def get_learning_context(self) -> Dict[str, Any]:
        if self.store and hasattr(self.store, 'get_recent_activities'):
            activities = self.store.get_recent_activities()
            if hasattr(activities, '__await__'):
                activities = await activities
            recent_topics = []
            for a in activities:
                content = a.get("content", "") if isinstance(a, dict) else str(a)
                # extract last word as topic hint
                words = content.lower().split()
                if words:
                    recent_topics.append(words[-1])
            return {
                "recent_topics": recent_topics,
                "current_focus": recent_topics[0] if recent_topics else ""
            }
        if self.store and hasattr(self.store, 'get_all_learning_progress'):
            all_progress = self.store.get_all_learning_progress()
            if hasattr(all_progress, '__iter__') and not isinstance(all_progress, type):
                try:
                    topics = [r["topic"] for r in all_progress]
                    return {
                        "topics_in_progress": len(topics),
                        "mastery_overview": {r["topic"]: r["mastery_score"] for r in all_progress},
                        "weak_topics": [r["topic"] for r in all_progress if r["mastery_score"] < 0.5],
                        "recent_topics": topics,
                        "current_focus": topics[0] if topics else ""
                    }
                except Exception:
                    pass
        return {"topics_in_progress": 0, "mastery_overview": {}, "weak_topics": [], "recent_topics": [], "current_focus": ""}

    def get_preference_context(self) -> Dict[str, Any]:
        if self.store and hasattr(self.store, 'get_profile_value'):
            prefs = self.store.get_profile_value("preferences") or {}
            goals = self.store.get_profile_value("learning_goals") or []
            return {"preferences": prefs, "goals": goals}
        return {"preferences": {}, "goals": []}

    async def get_current_context(self) -> UserContext:
        learning_ctx = await self.get_learning_context()
        task_ctx = await self.get_task_context()
        return UserContext(
            time_context=self._build_time_context(),
            task_context=task_ctx,
            learning_context=learning_ctx,
            preference_context=self.get_preference_context()
        )

    def get_current_context_sync(self) -> UserContext:
        return UserContext(
            time_context=self._build_time_context(),
            learning_context={},
            preference_context=self.get_preference_context()
        )
