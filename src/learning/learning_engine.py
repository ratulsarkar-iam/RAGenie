from typing import Optional, Dict, Any
from .feedback_collector import Feedback
from .knowledge_tracker import KnowledgeTracker
from .spaced_repetition import SpacedRepetitionScheduler
from ..memory.memory_store import MemoryStore
from ..core.logging_config import get_logger
from datetime import datetime

logger = get_logger(__name__)


class LearningEngine:
    """Processes feedback and orchestrates learning adaptations."""

    def __init__(self, config_or_store=None):
        from .config import LearningConfig
        if isinstance(config_or_store, LearningConfig):
            self.config = config_or_store
            self.knowledge_tracker = None
            self.scheduler = None
            self.memory_store = None
            self.strategy_optimizer = None
        elif config_or_store is not None:
            self.config = LearningConfig()
            self.knowledge_tracker = KnowledgeTracker(config_or_store)
            self.scheduler = SpacedRepetitionScheduler(config_or_store)
            self.memory_store = config_or_store
            self.strategy_optimizer = None
        else:
            self.config = LearningConfig()
            self.knowledge_tracker = None
            self.scheduler = None
            self.memory_store = None
            self.strategy_optimizer = None

        self.current_strategy = "balanced"  # default learning strategy

    async def process_feedback(self, feedback: Feedback, topic: Optional[str] = None) -> None:
        if self.knowledge_tracker and hasattr(self.knowledge_tracker, 'update'):
            await self.knowledge_tracker.update(feedback)

        if not topic:
            topic = feedback.metadata.get("topic") or self._infer_topic(feedback)

        if topic and self.knowledge_tracker and hasattr(self.knowledge_tracker, 'update_mastery'):
            new_mastery = await self.knowledge_tracker.update_mastery(topic, feedback)
            if self.scheduler:
                self.scheduler.schedule_next_review(topic, new_mastery, datetime.utcnow())
            logger.info(f"Processed feedback for topic '{topic}': mastery={new_mastery:.2f}")

        if feedback.type == "correction":
            logger.info(f"Correction received for message {feedback.message_id}")
            self.schedule_reinforcement(topic or "general", 0.0)

        if self.strategy_optimizer and hasattr(self.strategy_optimizer, 'adjust'):
            result = self.strategy_optimizer.adjust(feedback)
            if hasattr(result, '__await__'):
                await result

    def schedule_reinforcement(self, topic: str, mastery: float) -> None:
        if self.scheduler:
            from datetime import datetime
            self.scheduler.schedule_next_review(topic, mastery, datetime.utcnow())
        logger.info(f"Reinforcement scheduled for topic '{topic}'")

    def _infer_topic(self, feedback: Feedback) -> Optional[str]:
        text = feedback.comment or feedback.original_response or ""
        words = text.lower().split()
        keywords = ["python", "machine learning", "javascript", "data", "statistics",
                    "calculus", "linear algebra", "neural", "transformer", "sql"]
        for kw in keywords:
            if kw in text.lower():
                return kw
        return None

    def get_learning_summary(self) -> Dict[str, Any]:
        all_mastery = self.knowledge_tracker.get_all_mastery()
        due_reviews = self.scheduler.get_due_reviews()
        return {
            "topics_tracked": len(all_mastery),
            "mastery_overview": all_mastery,
            "due_reviews": [{"topic": r.topic, "mastery": r.mastery} for r in due_reviews],
            "average_mastery": round(sum(all_mastery.values()) / len(all_mastery), 2) if all_mastery else 0.0
        }
