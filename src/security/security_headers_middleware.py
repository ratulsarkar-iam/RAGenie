"""OWASP recommended security headers middleware."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "connect-src 'self' ws: wss: http://localhost:* https://localhost:*; "
    "font-src 'self' data:; "
    "frame-ancestors 'none';"
)


_DOCS_PATHS = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds OWASP-recommended security headers to every response.

    CSP is intentionally skipped for Swagger UI paths (/docs, /redoc,
    /openapi.json) so that their CDN-hosted assets can load correctly.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Skip frame-deny + CSP for Swagger / ReDoc so CDN assets load
        if request.url.path in _DOCS_PATHS:
            return response

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = _CSP
        return response
