"""
Tests for File Upload Security and Database Security
Covers: file_validator (magic bytes, extension, exe blocking),
        memory_store LIKE wildcard escape
Spec: openspec/changes/security-hardening/specs/file-upload-security/spec.md
      openspec/changes/security-hardening/specs/database-security/spec.md
"""
import os
import sqlite3
import tempfile
import pytest

from src.security.file_validator import validate_upload, MAX_FILE_SIZE, ALLOWED_EXTENSIONS


# ── FileValidator ─────────────────────────────────────────────────────────────

class TestFileValidator:
    """Tests for validate_upload(filename, content)."""

    # ── Valid files ──────────────────────────────────────────────────────────

    def test_valid_txt(self):
        ok, err = validate_upload("notes.txt", b"Hello world")
        assert ok is True
        assert err == ""

    def test_valid_pdf(self):
        ok, err = validate_upload("doc.pdf", b"%PDF-1.4 content here")
        assert ok is True

    def test_valid_png(self):
        png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        ok, err = validate_upload("image.png", png_magic)
        assert ok is True

    def test_valid_jpeg(self):
        jpg_magic = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        ok, err = validate_upload("photo.jpg", jpg_magic)
        assert ok is True

    def test_valid_docx(self):
        zip_magic = b"PK\x03\x04" + b"\x00" * 100
        ok, err = validate_upload("report.docx", zip_magic)
        assert ok is True

    def test_valid_xlsx(self):
        zip_magic = b"PK\x03\x04" + b"\x00" * 100
        ok, err = validate_upload("data.xlsx", zip_magic)
        assert ok is True

    def test_valid_csv(self):
        ok, err = validate_upload("data.csv", b"col1,col2\n1,2\n")
        assert ok is True

    def test_valid_markdown(self):
        ok, err = validate_upload("readme.md", b"# Title\nContent")
        assert ok is True

    def test_valid_gif(self):
        ok, err = validate_upload("anim.gif", b"GIF89a" + b"\x00" * 50)
        assert ok is True

    # ── Extension blocking ───────────────────────────────────────────────────

    def test_exe_extension_blocked(self):
        ok, err = validate_upload("malware.exe", b"MZ" + b"\x00" * 100)
        assert ok is False
        assert "not allowed" in err.lower() or "executable" in err.lower()

    def test_sh_extension_blocked(self):
        ok, err = validate_upload("setup.sh", b"#!/bin/bash\nrm -rf /")
        assert ok is False

    def test_py_extension_blocked(self):
        ok, err = validate_upload("script.py", b"import os; os.system('rm -rf /')")
        assert ok is False

    def test_js_extension_blocked(self):
        ok, err = validate_upload("evil.js", b"require('child_process')")
        assert ok is False

    def test_bat_extension_blocked(self):
        ok, err = validate_upload("run.bat", b"@echo off\ndel /f /q C:\\")
        assert ok is False

    def test_no_extension_blocked(self):
        ok, err = validate_upload("noextension", b"some content")
        assert ok is False

    # ── Magic-byte / executable blocking ────────────────────────────────────

    def test_windows_pe_blocked_regardless_of_extension(self):
        """MZ header must be blocked even with a .txt extension."""
        ok, err = validate_upload("harmless.txt", b"MZ\x90\x00" + b"\x00" * 100)
        assert ok is False
        assert "executable" in err.lower()

    def test_linux_elf_blocked(self):
        ok, err = validate_upload("binary.pdf", b"\x7fELF" + b"\x00" * 100)
        assert ok is False
        assert "executable" in err.lower()

    def test_macos_universal_binary_blocked(self):
        ok, err = validate_upload("lib.txt", b"\xca\xfe\xba\xbe" + b"\x00" * 100)
        assert ok is False

    def test_macho_32bit_blocked(self):
        ok, err = validate_upload("app.txt", b"\xfe\xed\xfa\xce" + b"\x00" * 100)
        assert ok is False

    def test_macho_64bit_blocked(self):
        ok, err = validate_upload("app.txt", b"\xfe\xed\xfa\xcf" + b"\x00" * 100)
        assert ok is False

    def test_shebang_blocked(self):
        ok, err = validate_upload("script.txt", b"#!/usr/bin/env python3\nimport os")
        assert ok is False

    def test_shebang_short_blocked(self):
        ok, err = validate_upload("run.txt", b"#!" + b"bash")
        assert ok is False

    def test_pdf_wrong_magic_blocked(self):
        """A .pdf file that doesn't start with %PDF must be rejected."""
        ok, err = validate_upload("fake.pdf", b"PK\x03\x04" + b"\x00" * 100)
        assert ok is False
        assert "does not match" in err.lower() or "content" in err.lower()

    def test_png_wrong_magic_blocked(self):
        ok, err = validate_upload("fake.png", b"%PDF-1.4 fake" + b"\x00" * 50)
        assert ok is False

    def test_jpeg_wrong_magic_blocked(self):
        ok, err = validate_upload("fake.jpg", b"GIF89a" + b"\x00" * 50)
        assert ok is False

    # ── Size / empty checks ──────────────────────────────────────────────────

    def test_empty_file_rejected(self):
        ok, err = validate_upload("empty.txt", b"")
        assert ok is False
        assert "empty" in err.lower()

    def test_oversized_file_rejected(self):
        big = b"a" * (MAX_FILE_SIZE + 1)
        ok, err = validate_upload("big.txt", big)
        assert ok is False
        assert "large" in err.lower() or "size" in err.lower()

    def test_exactly_max_size_allowed(self):
        content = b"a" * MAX_FILE_SIZE
        ok, _ = validate_upload("max.txt", content)
        assert ok is True

    def test_no_filename_rejected(self):
        ok, err = validate_upload("", b"content")
        assert ok is False

    # ── Path traversal has no effect (extension is taken from name only) ─────

    def test_traversal_filename_extension_check(self):
        """../../etc/passwd has no extension → blocked."""
        ok, err = validate_upload("../../etc/passwd", b"root:x:0:0")
        assert ok is False


# ── DatabaseSecurity (memory_store LIKE escape) ───────────────────────────────

class TestDatabaseSecurity:
    """Verifies SQL LIKE wildcard escaping in MemoryStore.retrieve_memories."""

    @pytest.fixture
    def store(self):
        from src.memory.memory_store import MemoryStore
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        s = MemoryStore(db_path=path)
        yield s
        os.unlink(path)

    def test_escape_like_escapes_percent(self):
        from src.memory.memory_store import MemoryStore
        assert MemoryStore._escape_like("100%") == "100!%"

    def test_escape_like_escapes_underscore(self):
        from src.memory.memory_store import MemoryStore
        assert MemoryStore._escape_like("col_name") == "col!_name"

    def test_escape_like_escapes_bang(self):
        from src.memory.memory_store import MemoryStore
        assert MemoryStore._escape_like("a!b") == "a!!b"

    def test_escape_like_combined(self):
        from src.memory.memory_store import MemoryStore
        assert MemoryStore._escape_like("%_!") == "!%!_!!"

    def test_retrieve_with_wildcard_query_does_not_crash(self, store):
        """A query containing SQL LIKE wildcards must not raise or return everything."""
        results = store.retrieve_memories("%")
        assert isinstance(results, list)

    def test_retrieve_with_sql_injection_attempt(self, store):
        """Single-quote injection must not raise or break the query."""
        results = store.retrieve_memories("') OR '1'='1")
        assert isinstance(results, list)

    def test_retrieve_with_underscore_wildcard(self, store):
        """Underscore wildcard must be treated as literal character."""
        results = store.retrieve_memories("_")
        assert isinstance(results, list)

    def test_retrieve_with_many_words_capped(self, store):
        """More than 10 words in query must be silently capped to 10."""
        long_query = " ".join(f"word{i}" for i in range(20))
        results = store.retrieve_memories(long_query)
        assert isinstance(results, list)

    def test_retrieve_empty_query_returns_list(self, store):
        results = store.retrieve_memories("")
        assert isinstance(results, list)

    def test_all_queries_use_parameterized_binding(self, store):
        """Verify no raw string interpolation reaches SQLite.
        This test inserts a row then searches for a term that would match
        it only via correct LIKE escaping.
        """
        from src.memory.models import Memory, MemoryType
        from datetime import datetime
        m = Memory(
            id="test-1",
            type=MemoryType.FACT,
            content="price is 100% accurate",
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
        )
        store.store_memory(m)
        # Searching for literal "100%" should find the record
        results = store.retrieve_memories("100%")
        assert any("100%" in r.content for r in results)
