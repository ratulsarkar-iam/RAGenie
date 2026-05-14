from typing import Dict, Any, List
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class LearningAnalytics:
    """Generates learning progress reports and analytics."""

    def __init__(self, storage):
        self.storage = storage

    async def generate_progress_report(self, user_id: str) -> Dict[str, Any]:
        mastery_levels = {}
        knowledge_gaps = []

        if hasattr(self.storage, 'get_mastery_overview'):
            result = self.storage.get_mastery_overview()
            if hasattr(result, '__await__'):
                result = await result
            mastery_levels = result or {}

        if hasattr(self.storage, 'identify_gaps'):
            result = self.storage.identify_gaps()
            if hasattr(result, '__await__'):
                result = await result
            knowledge_gaps = result or []

        return {
            "user_id": user_id,
            "mastery_levels": mastery_levels,
            "knowledge_gaps": knowledge_gaps,
            "total_topics": len(mastery_levels),
            "average_mastery": (
                round(sum(mastery_levels.values()) / len(mastery_levels), 2)
                if mastery_levels else 0.0
            )
        }
