import asyncio
from datetime import datetime
from typing import Optional
from .context_analyzer import ContextAnalyzer, UserContext, TimeContext
from .content_generator import ContentGenerator, Nudge, Briefing
from .notification_service import NotificationService
from ..memory.memory_store import MemoryStore
from ..learning.spaced_repetition import SpacedRepetitionScheduler
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class ProactiveEngine:
    """Runs proactive analysis cycles and delivers helpful content."""

    def __init__(
        self,
        context_analyzer: Optional[ContextAnalyzer] = None,
        trigger_manager=None,
        content_generator: Optional[ContentGenerator] = None,
        notification_service: Optional[NotificationService] = None,
        memory_store: Optional[MemoryStore] = None,
        briefing_hour: int = 9
    ):
        self.context_analyzer = context_analyzer or ContextAnalyzer(memory_store)
        self.content_generator = content_generator or ContentGenerator()
        self.notification_service = notification_service or NotificationService()
        self.trigger_manager = trigger_manager
        self.scheduler = SpacedRepetitionScheduler(memory_store) if memory_store else None
        self.briefing_hour = briefing_hour
        self._last_briefing_date: Optional[str] = None
        self._running = False

    async def run_proactive_cycle(self) -> None:
        context = await self.context_analyzer.get_current_context()

        # Derive current time from context or fall back to real time
        tc = context.time_context
        if tc and hasattr(tc, 'current_time') and tc.current_time:
            now = tc.current_time
        else:
            now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        now_hour = now.hour

        # Daily briefing
        if self._last_briefing_date != today and now_hour >= self.briefing_hour:
            briefing = await self.content_generator.generate_daily_briefing(context)
            if self.notification_service.is_appropriate_time(briefing, context) is not False:
                await self.notification_service.deliver(briefing)
                self._last_briefing_date = today
                logger.info("Daily briefing delivered")

        # Learning nudges via trigger manager (if available)
        if self.trigger_manager and hasattr(self.trigger_manager, 'identify_triggers'):
            result = self.trigger_manager.identify_triggers()
            if hasattr(result, '__await__'):
                result = await result
            if not isinstance(result, (list, tuple)):
                result = []
            for trigger in result:
                topic = getattr(trigger, 'topic', None)
                if topic and getattr(trigger, 'type', '') == 'learning_review':
                    nudge = await self.content_generator.generate_learning_nudge(topic, 0.5)
                    if self.notification_service.is_appropriate_time(nudge, context) is not False:
                        await self.notification_service.deliver(nudge)

        # Learning nudges for due reviews (scheduler path)
        if self.scheduler:
            due_reviews = self.scheduler.get_due_reviews()
            for item in due_reviews[:2]:
                nudge = await self.content_generator.generate_learning_nudge(item.topic, item.mastery)
                if self.notification_service.is_appropriate_time(nudge, context) is not False:
                    await self.notification_service.deliver(nudge)

        # Task suggestion
        try:
            raw = self.content_generator.generate_task_suggestion(context)
            suggestion = await raw if hasattr(raw, '__await__') else raw
        except Exception:
            suggestion = None
        if isinstance(suggestion, (Nudge, Briefing)) and self.notification_service.is_appropriate_time(suggestion, context) is not False:
            await self.notification_service.deliver(suggestion)

    async def start_background_loop(self, interval_minutes: int = 30) -> None:
        self._running = True
        logger.info(f"Proactive engine started (interval: {interval_minutes}m)")
        while self._running:
            try:
                await self.run_proactive_cycle()
            except Exception as e:
                logger.error(f"Proactive cycle error: {e}")
            await asyncio.sleep(interval_minutes * 60)

    async def should_deliver(self, notification, context) -> bool:
        tc = context.time_context if context else None
        if tc is None:
            return True
        priority = getattr(notification, "priority", "medium")
        if getattr(tc, "is_quiet_hours", False):
            return priority == "urgent"
        if getattr(tc, "in_meeting", False):
            return priority in ("urgent", "high")
        return True

    def stop(self) -> None:
        self._running = False
        logger.info("Proactive engine stopped")
