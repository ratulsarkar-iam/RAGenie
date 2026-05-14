"""Thread-based news fetch and retention scheduler — stdlib only, no third-party deps."""
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, Dict, Optional

from ..core.logging_config import get_logger

if TYPE_CHECKING:
    from .models import Keyword

logger = get_logger(__name__)


class _RepeatingTimer:
    """Calls `fn` every `interval_seconds` until stopped.

    `initial_delay_seconds` controls the wait before the *first* call.
    Pass 0 to fire immediately on start.
    """

    def __init__(
        self,
        interval_seconds: float,
        fn: Callable,
        name: str = "timer",
        initial_delay_seconds: Optional[float] = None,
    ):
        self._interval = interval_seconds
        self._initial_delay = (
            initial_delay_seconds if initial_delay_seconds is not None
            else interval_seconds
        )
        self._fn = fn
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name=name)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        first_wait = max(0.0, self._initial_delay)
        if first_wait > 0 and self._stop.wait(first_wait):
            return  # stopped before first fire
        while True:
            try:
                self._fn()
            except Exception as e:
                logger.error(f"Scheduled job '{self._thread.name}' raised: {e}")
            if self._stop.wait(self._interval):
                break  # stopped


class NewsScheduler:
    """Lightweight scheduler backed by daemon threads — no third-party dependencies."""

    def __init__(self, run_for_keyword_fn: Callable, run_cleanup_fn: Callable, cleanup_interval_hours: int = 6):
        self._run_for_keyword = run_for_keyword_fn
        self._run_cleanup = run_cleanup_fn
        self._cleanup_hours = cleanup_interval_hours
        self._keyword_timers: Dict[str, _RepeatingTimer] = {}
        self._cleanup_timer: _RepeatingTimer = _RepeatingTimer(
            interval_seconds=cleanup_interval_hours * 3600,
            fn=run_cleanup_fn,
            name="news_retention_cleanup",
        )

    def start(self) -> None:
        self._cleanup_timer.start()
        logger.info(f"NewsScheduler started (retention cleanup every {self._cleanup_hours}h)")

    def stop(self) -> None:
        self._cleanup_timer.stop()
        for timer in list(self._keyword_timers.values()):
            timer.stop()
        self._keyword_timers.clear()
        logger.info("NewsScheduler stopped")

    def register_keyword(self, keyword: "Keyword", jitter_seconds: float = 0.0) -> None:
        self.remove_keyword(keyword.id)
        kid = keyword.id
        interval = keyword.fetch_interval_minutes * 60

        # Calculate how long until the next scheduled fetch.
        # If last_fetched_at is None or the keyword is already overdue, fire immediately.
        initial_delay: float = 0.0
        if keyword.last_fetched_at is not None:
            now = datetime.now(timezone.utc)
            lfa = keyword.last_fetched_at
            if lfa.tzinfo is None:
                lfa = lfa.replace(tzinfo=timezone.utc)
            elapsed = (now - lfa).total_seconds()
            remaining = interval - elapsed
            initial_delay = max(0.0, remaining) + jitter_seconds
        else:
            initial_delay = jitter_seconds  # never fetched — run soon (after jitter)

        timer = _RepeatingTimer(
            interval_seconds=interval,
            fn=lambda: self._run_for_keyword(kid),
            name=f"news_fetch_{kid[:8]}",
            initial_delay_seconds=initial_delay,
        )
        self._keyword_timers[keyword.id] = timer
        timer.start()
        logger.debug(
            f"Registered fetch job for keyword '{keyword.term}' "
            f"(every {keyword.fetch_interval_minutes}m, first fire in {initial_delay:.0f}s)"
        )

    def remove_keyword(self, keyword_id: str) -> None:
        timer = self._keyword_timers.pop(keyword_id, None)
        if timer:
            timer.stop()

    def refresh(self, keywords) -> None:
        """Re-register all enabled keywords (used on startup).

        Overdue keywords are staggered by 10 s each so they don't all hit
        the external news source at the exact same moment.
        """
        overdue_index = 0
        for kw in keywords:
            if not kw.enabled:
                continue
            interval = kw.fetch_interval_minutes * 60
            is_overdue = (
                kw.last_fetched_at is None or
                (datetime.now(timezone.utc) - (
                    kw.last_fetched_at if kw.last_fetched_at.tzinfo
                    else kw.last_fetched_at.replace(tzinfo=timezone.utc)
                )).total_seconds() >= interval
            )
            jitter = overdue_index * 10.0 if is_overdue else 0.0
            if is_overdue:
                overdue_index += 1
            self.register_keyword(kw, jitter_seconds=jitter)
