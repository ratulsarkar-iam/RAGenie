from typing import List, Dict, Any
from ..memory.memory_store import MemoryStore
from .feedback_collector import Feedback
from ..core.logging_config import get_logger

logger = get_logger(__name__)

POSITIVE_INCREMENT = 0.1
NEGATIVE_DECREMENT = 0.08


class KnowledgeGap:
    def __init__(self, topic: str, mastery: float, frequency: int):
        self.topic = topic
        self.mastery = mastery
        self.frequency = frequency
        self.urgency = "high" if mastery < 0.3 else "medium"


class KnowledgeTracker:
    """Tracks user knowledge levels per topic using the memory store."""

    def __init__(self, storage):
        self.store = storage

    async def _get_mastery(self, topic: str) -> float:
        if hasattr(self.store, 'get_mastery'):
            result = self.store.get_mastery(topic)
            if hasattr(result, '__await__'):
                return await result
            return result
        return 0.5

    async def _set_mastery(self, topic: str, value: float) -> None:
        if hasattr(self.store, 'set_mastery'):
            result = self.store.set_mastery(topic, value)
            if hasattr(result, '__await__'):
                await result

    async def update_mastery(self, topic: str, feedback: Feedback) -> float:
        current = await self._get_mastery(topic)

        if feedback.positive:
            new_mastery = min(1.0, current + POSITIVE_INCREMENT)
        else:
            new_mastery = max(0.0, current - NEGATIVE_DECREMENT)

        await self._set_mastery(topic, new_mastery)
        logger.debug(f"Mastery updated for '{topic}': {current:.2f} → {new_mastery:.2f}")
        return new_mastery

    async def identify_gaps(self, context: Dict[str, Any]) -> List[KnowledgeGap]:
        try:
            # Path 1: use recent questions to detect struggling topics
            if hasattr(self.store, 'get_recent_questions'):
                result = self.store.get_recent_questions()
                if hasattr(result, '__await__'):
                    result = await result
                if isinstance(result, (list, tuple)):
                    freq: Dict[str, int] = {}
                    for q in result:
                        q_lower = str(q).lower()
                        for word in q_lower.split():
                            word = word.strip('?.,!;:')
                            if len(word) > 3 and word not in (
                                'what', 'how', 'why', 'when', 'where', 'does', 'with',
                                'that', 'this', 'from', 'have', 'list', 'use', 'used'):
                                freq[word] = freq.get(word, 0) + 1
                    gaps = []
                    for topic, count in freq.items():
                        if count >= 3:
                            stored = await self._get_mastery(topic)
                            # Frequency penalty: more questions → lower effective mastery
                            effective = stored * max(0.0, 1.0 - (count - 1) * 0.1)
                            if effective < 0.5:
                                gaps.append(KnowledgeGap(
                                    topic=topic,
                                    mastery=round(effective, 3),
                                    frequency=count
                                ))
                    return sorted(gaps, key=lambda g: g.mastery)

            # Path 2: structured learning progress store
            if hasattr(self.store, 'get_all_learning_progress'):
                result = self.store.get_all_learning_progress()
                if hasattr(result, '__await__'):
                    result = await result
                if isinstance(result, (list, tuple)):
                    gaps = []
                    for row in result:
                        if not isinstance(row, dict):
                            continue
                        mastery = row.get('mastery_score', 0.0)
                        review_count = row.get('review_count', 0)
                        if mastery < 0.5 and review_count >= 2:
                            gaps.append(KnowledgeGap(
                                topic=row['topic'],
                                mastery=mastery,
                                frequency=review_count
                            ))
                    return sorted(gaps, key=lambda g: g.mastery)
        except Exception:
            pass
        return []

    def get_mastery(self, topic: str) -> float:
        return self.store.get_mastery(topic)

    def get_all_mastery(self) -> Dict[str, float]:
        all_progress = self.store.get_all_learning_progress()
        return {row["topic"]: row["mastery_score"] for row in all_progress}
