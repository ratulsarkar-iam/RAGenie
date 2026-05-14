"""Filter document chunks before injecting them into prompts."""
import re
from dataclasses import dataclass
from typing import List, Optional

MAX_CHUNK_LENGTH = 3_000

_BLOCKED_PATTERNS: List[re.Pattern] = [
    re.compile(r'ignore\s+(previous|above|prior)\s+instructions?', re.IGNORECASE),
    re.compile(r'disregard\s+(the\s+)?(above|previous|prior|system)', re.IGNORECASE),
    re.compile(r'<\s*script[^>]*>', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+', re.IGNORECASE),
    re.compile(r'\bsystem\s+prompt\s*:', re.IGNORECASE),
    re.compile(r'={3,}\s*(SYSTEM|INSTRUCTION|OVERRIDE)', re.IGNORECASE),
]

# Strip prompt-structure markers that leaked into document content
_STRIP_RE = re.compile(
    r'(===\s*(SYSTEM|CONTEXT|USER|DOCUMENTS|INSTRUCTION|END)\s*===)',
    re.IGNORECASE,
)


@dataclass
class FilteredChunk:
    content: str
    was_modified: bool
    blocked: bool
    reason: Optional[str] = None


def filter_document_chunk(content: str) -> FilteredChunk:
    """Scan a single RAG chunk for embedded instructions or injection patterns.

    Blocked chunks are replaced with a placeholder.
    Suspicious delimiters are neutralised.
    """
    if not content:
        return FilteredChunk(content="", was_modified=False, blocked=False)

    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(content):
            return FilteredChunk(
                content="[DOCUMENT CONTENT FILTERED]",
                was_modified=True,
                blocked=True,
                reason=f"Matched: {pattern.pattern[:50]}",
            )

    modified = False

    cleaned, n = _STRIP_RE.subn(
        lambda m: f"[{m.group(2).upper()}]", content
    )
    if n > 0:
        content = cleaned
        modified = True

    if len(content) > MAX_CHUNK_LENGTH:
        content = content[:MAX_CHUNK_LENGTH] + "\n[… truncated]"
        modified = True

    return FilteredChunk(content=content, was_modified=modified, blocked=False)
