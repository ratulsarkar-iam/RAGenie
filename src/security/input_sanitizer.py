"""Detect and flag prompt injection attempts in user input."""
import re
from typing import NamedTuple, List

MAX_INPUT_LENGTH = 4_000

_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r'ignore\s+(previous|above|prior)\s+instructions?', re.IGNORECASE),
    re.compile(r'disregard\s+(the\s+)?(above|previous|prior|system)', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+(a\s+|an\s+)?', re.IGNORECASE),
    re.compile(r'(act|pretend|behave)\s+as\s+(if\s+you\s+are\s+)?', re.IGNORECASE),
    re.compile(r'\bsystem\s+prompt\s*:', re.IGNORECASE),
    re.compile(r'<\s*/?system\s*>', re.IGNORECASE),
    re.compile(r'\[\s*/?INST\s*\]'),
    re.compile(r'={3,}\s*(SYSTEM|INSTRUCTION|OVERRIDE)', re.IGNORECASE),
    re.compile(r'jailbreak', re.IGNORECASE),
    re.compile(r'do\s+anything\s+now', re.IGNORECASE),
]

_DELIMITER_FRAGMENTS = [
    "=== system ===", "=== instruction ===", "=== override ===",
    "<<sys>>", "</s>", "[inst]", "[/inst]",
]


class SanitizedInput(NamedTuple):
    text: str
    risk_score: float   # 0.0 clean → 1.0 high-risk
    flags: List[str]


def sanitize_user_input(text: str) -> SanitizedInput:
    """Validate and characterise user input for prompt-injection risk.

    The text is always returned (never blocked here) so callers can decide
    whether to proceed, warn, or reject based on ``risk_score``.
    """
    if not isinstance(text, str):
        return SanitizedInput(text="", risk_score=0.0, flags=["invalid_type"])

    text = text[:MAX_INPUT_LENGTH]
    flags: List[str] = []
    lower = text.lower()

    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            flags.append(f"injection:{pattern.pattern[:40]}")

    for frag in _DELIMITER_FRAGMENTS:
        if frag in lower:
            flags.append(f"delimiter:{frag}")

    risk_score = min(1.0, len(flags) * 0.25)
    return SanitizedInput(text=text, risk_score=risk_score, flags=flags)
