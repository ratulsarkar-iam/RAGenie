"""In-memory sliding-window rate limiting middleware."""
import time
import asyncio
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .audit_logger import get_audit_logger

_TIERS: Dict[str, Tuple[int, int]] = {
    "upload": (10, 3600),   # 10 uploads / hour
    "default": (60, 60),    # 60 requests / minute
}

_SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def _classify(path: str) -> str:
    if "/upload" in path or "/chat-upload" in path:
        return "upload"
    return "default"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter. No Redis required.

    Pass a ``config`` (``RateLimitConfig``) to apply values from
    ``config.yaml`` instead of the hardcoded defaults.
    """

    def __init__(self, app, enabled: bool = True, config: Optional[object] = None):
        super().__init__(app)
        self.enabled = enabled
        self._windows: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        if config is not None:
            self._tiers: Dict[str, Tuple[int, int]] = {
                "upload":  (config.upload_rph, 3600),
                "default": (config.default_rpm, 60),
            }
        else:
            self._tiers = _TIERS

    async def dispatch(self, request: Request, call_next):
        if not self.enabled or request.url.path in _SKIP_PATHS:
            return await call_next(request)

        tier = _classify(request.url.path)
        max_req, window_sec = self._tiers[tier]
        ip = _client_ip(request)
        key = f"{ip}:{tier}"
        now = time.monotonic()

        async with self._lock:
            self._windows[key] = [
                ts for ts in self._windows[key] if now - ts < window_sec
            ]
            count = len(self._windows[key])
            if count >= max_req:
                oldest = min(self._windows[key])
                retry_after = int(window_sec - (now - oldest)) + 1
                get_audit_logger().rate_limit_hit(ip=ip, path=request.url.path, tier=tier)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(max_req),
                        "X-RateLimit-Remaining": "0",
                    },
                )
            self._windows[key].append(now)
            remaining = max_req - count - 1

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_req)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
