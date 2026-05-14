from typing import List
from dataclasses import dataclass
from .context_analyzer import UserContext
from ..core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Opportunity:
    type: str
    topic: str
    urgency: str
    suggested_action: str


class OpportunityDetector:
    """Detects learning and task opportunities from user context."""

    def __init__(self, knowledge_tracker=None):
        self.knowledge_tracker = knowledge_tracker

    async def detect_learning_opportunities(self, context: UserContext) -> List[Opportunity]:
        opportunities = []

        # Use knowledge tracker's due reviews if available
        if self.knowledge_tracker and hasattr(self.knowledge_tracker, 'get_due_reviews'):
            result = self.knowledge_tracker.get_due_reviews()
            if hasattr(result, '__await__'):
                result = await result
            for item in (result or []):
                topic = item.get("topic") if isinstance(item, dict) else getattr(item, "topic", None)
                mastery = item.get("mastery", 0.5) if isinstance(item, dict) else getattr(item, "mastery", 0.5)
                if topic:
                    urgency = "high" if mastery < 0.3 else "medium"
                    opportunities.append(Opportunity(
                        type="learning_review",
                        topic=topic,
                        urgency=urgency,
                        suggested_action=f"Review {topic}"
                    ))
            return opportunities

        # Fallback to context-based detection
        lc = context.learning_context or {}
        weak_topics = lc.get("weak_topics", [])
        mastery_overview = lc.get("mastery_overview", {})
        for topic in weak_topics:
            level = mastery_overview.get(topic, 0.0)
            urgency = "high" if level < 0.3 else "medium"
            opportunities.append(Opportunity(
                type="knowledge_gap",
                topic=topic,
                urgency=urgency,
                suggested_action=f"Review {topic} basics"
            ))
        return opportunities

    async def detect_task_opportunities(self, context: UserContext) -> List[Opportunity]:
        tc = context.time_context
        if tc and tc.time_of_day == "morning":
            return [Opportunity(
                type="daily_planning",
                topic="daily_tasks",
                urgency="low",
                suggested_action="Plan your day"
            )]
        return []
