"""Magic-byte file validation for uploaded files.

Validates both the declared extension AND the actual file content to prevent
MIME-type confusion and disguised executables.
"""
from pathlib import Path
from typing import Dict, List, Tuple

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB

ALLOWED_EXTENSIONS = frozenset({
    ".txt", ".pdf", ".md", ".markdown",
    ".docx", ".doc", ".xlsx", ".xls", ".csv",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg",
    ".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma",
})

# (extension, required_prefix_bytes) — empty bytes = no magic check (text/csv/svg etc.)
_MAGIC: Dict[str, bytes] = {
    ".pdf":  b"%PDF",
    ".jpg":  b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png":  b"\x89PNG\r\n\x1a\n",
    ".gif":  b"GIF8",
    # DOCX / XLSX are ZIP-based Office Open XML
    ".docx": b"PK\x03\x04",
    ".xlsx": b"PK\x03\x04",
    # MP3 — either ID3 tag or MPEG sync
    ".mp3":  b"",
}

# Executable signatures that are ALWAYS blocked regardless of extension
_BLOCKED_MAGIC: List[bytes] = [
    b"MZ",                   # Windows PE
    b"\x7fELF",              # Linux ELF
    b"\xca\xfe\xba\xbe",     # macOS universal binary
    b"\xfe\xed\xfa\xce",     # macOS Mach-O 32-bit
    b"\xfe\xed\xfa\xcf",     # macOS Mach-O 64-bit
    b"#!/",                  # Shell script shebang
    b"#!",                   # Generic shebang
]


def validate_upload(filename: str, content: bytes) -> Tuple[bool, str]:
    """Validate an uploaded file by extension and magic bytes.

    Returns:
        (is_valid, error_message)  — error_message is empty string on success.
    """
    if not filename:
        return False, "No filename provided"

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File extension '{ext}' is not allowed"

    size = len(content)
    if size == 0:
        return False, "File is empty"

    if size > MAX_FILE_SIZE:
        mb = size / (1024 * 1024)
        return False, f"File too large ({mb:.1f} MB, max 30 MB)"

    # Block executables regardless of declared extension
    for sig in _BLOCKED_MAGIC:
        if content[: len(sig)] == sig:
            return False, "Executable content is not allowed"

    # Magic-byte check for typed formats
    expected_magic = _MAGIC.get(ext)
    if expected_magic:  # empty bytes means "no check needed"
        if not content[: len(expected_magic)] == expected_magic:
            return False, (
                f"File content does not match declared extension '{ext}'"
            )

    return True, ""
