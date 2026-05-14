from typing import List, Optional
from dataclasses import dataclass, field
from .context_analyzer import UserContext
from ..core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Briefing:
    content: str = ""
    priority: str = "medium"
    delivery_time: str = "09:00"
    channels: List[str] = field(default_factory=lambda: ["dashboard"])


@dataclass
class Nudge:
    message: str = ""
    topic: str = ""
    action_type: str = "review"
    urgency: str = "low"


class ContentGenerator:
    """Generates proactive content for the user."""

    def __init__(self, llm=None):
        self.llm = llm

    async def generate_daily_briefing(self, context: UserContext) -> Briefing:
        lines = []
        tc = context.time_context
        lc = context.learning_context

        greeting = {
            "morning": "Good morning",
            "afternoon": "Good afternoon",
            "evening": "Good evening",
            "night": "Hey"
        }.get(tc.time_of_day if tc else "morning", "Hello")

        lines.append(f"{greeting}! Here's your daily briefing:\n")

        # Learning section
        weak_topics = lc.get("weak_topics", []) if isinstance(lc, dict) else []
        if isinstance(weak_topics, (list, tuple)) and weak_topics:
            lines.append(f"📚 Topics needing attention: {', '.join(str(t) for t in weak_topics[:3])}")

        mastery = lc.get("mastery_overview", {}) if isinstance(lc, dict) else {}
        if isinstance(mastery, dict) and mastery:
            avg = round(sum(mastery.values()) / len(mastery) * 100)
            lines.append(f"📊 Overall learning progress: {avg}%")

        goals = context.preference_context.get("goals", []) if isinstance(context.preference_context, dict) else []
        if goals and isinstance(goals, (list, tuple)):
            lines.append(f"🎯 Current goals: {', '.join(str(g) for g in goals[:2])}")

        lines.append("\n💡 Tip: Ask me anything to continue learning!")

        if self.llm:
            tc = context.time_context
            tc_ctx = context.task_context if isinstance(context.task_context, dict) else {}
            lc_ctx = context.learning_context if isinstance(context.learning_context, dict) else {}
            priorities = tc_ctx.get("today_priorities", [])
            topics = lc_ctx.get("recent_topics", [])
            priorities = priorities if isinstance(priorities, (list, tuple)) else []
            topics = topics if isinstance(topics, (list, tuple)) else []
            prompt = (
                f"Generate a brief daily briefing for a {getattr(tc, 'time_of_day', 'morning')} check-in.\n"
                f"Today's priorities: {', '.join(priorities)}\n"
                f"Recent learning topics: {', '.join(topics)}\n"
                f"Keep it concise and motivating."
            )
            content = await self.llm.generate(prompt)
        else:
            content = "\n".join(lines)

        return Briefing(
            content=content,
            priority="high",
            delivery_time="09:00",
            channels=["dashboard", "notification"]
        )

    async def generate_learning_nudge(self, topic: str, mastery: float) -> Nudge:
        if mastery < 0.4:
            message = f"It's been a while since you reviewed '{topic}'. A 2-minute refresher will help!"
            urgency = "low"
        elif mastery < 0.7:
            message = f"Ready to continue with '{topic}'? A quick 2-minute review keeps momentum going!"
            urgency = "low"
        else:
            message = f"Great mastery of '{topic}'! Consider exploring advanced topics to deepen your knowledge."
            urgency = "low"

        return Nudge(message=message, topic=topic, action_type="review", urgency=urgency)

    async def generate_task_suggestion(self, context: UserContext) -> Optional[Nudge]:
        task_ctx = context.task_context or {}
        if self.llm and task_ctx:
            prompt = f"Suggest a productivity optimization for: {task_ctx}"
            suggestion_text = await self.llm.generate(prompt)
            return Nudge(
                message=suggestion_text,
                topic="productivity",
                action_type="optimization",
                urgency="low"
            )
        weak = (context.learning_context or {}).get("weak_topics", [])
        if weak:
            topic = weak[0]
            return Nudge(
                message=f"I noticed '{topic}' might need more practice. Want to work on it now?",
                topic=topic,
                action_type="learning_support",
                urgency="medium"
            )
        return None
