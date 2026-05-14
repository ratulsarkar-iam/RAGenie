"""Automatic PII and sensitive data redaction for logs and outputs."""
import re
from typing import Any, Dict, List, Union

_PATTERNS = [
    # URL credentials must come BEFORE email so password@host is not swallowed by email regex
    (re.compile(r'://[^:@\s]+:[^@\s]+@'), '://[USER]:[PASS]@'),
    (re.compile(r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'), '[JWT]'),
    (re.compile(r'\b(?:sk-|Bearer\s)[A-Za-z0-9\-_]{20,}'), '[API_KEY]'),
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'), '[EMAIL]'),
    (re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'), '[PHONE]'),
    (re.compile(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b'), '[CARD]'),
]

_SENSITIVE_KEYS = frozenset({
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
    'authorization', 'auth', 'cookie', 'session', 'private_key',
    'access_token', 'refresh_token', 'credentials', 'credit_card', 'ssn',
})


def redact(text: str) -> str:
    """Redact PII patterns from a string."""
    if not isinstance(text, str):
        return text
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redact sensitive values from a dict."""
    if not isinstance(data, dict):
        return data
    result: Dict[str, Any] = {}
    for k, v in data.items():
        if k.lower() in _SENSITIVE_KEYS:
            result[k] = '[REDACTED]'
        elif isinstance(v, str):
            result[k] = redact(v)
        elif isinstance(v, dict):
            result[k] = redact_dict(v)
        elif isinstance(v, list):
            result[k] = [
                redact(i) if isinstance(i, str)
                else redact_dict(i) if isinstance(i, dict)
                else i
                for i in v
            ]
        else:
            result[k] = v
    return result
