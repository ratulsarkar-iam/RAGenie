"""Unit tests for KeywordStore — uses a real temp SQLite DB, no mocks needed."""
import pytest
from datetime import datetime, timedelta
from src.news.keyword_store import KeywordStore
from src.news.models import KeywordCreate


@pytest.fixture
def store(tmp_path):
    db = str(tmp_path / "shared.db")
    from src.news.article_store import ArticleStore
    ArticleStore(db)  # creates articles + article_summaries tables
    return KeywordStore(db)


def _create(store: KeywordStore, term: str = "West Bengal", interval: int = 60) -> object:
    return store.create(KeywordCreate(term=term, fetch_interval_minutes=interval, max_articles_per_fetch=10))


class TestKeywordStore:
    def test_create_returns_keyword(self, store):
        kw = _create(store)
        assert kw.term == "West Bengal"
        assert kw.enabled is True
        assert kw.id is not None

    def test_create_duplicate_term_raises(self, store):
        _create(store, "Modi")
        with pytest.raises(Exception):
            _create(store, "Modi")

    def test_list_all(self, store):
        _create(store, "India")
        _create(store, "Bengal")
        kws = store.list_all()
        assert len(kws) == 2

    def test_get_returns_keyword(self, store):
        kw = _create(store)
        fetched = store.get(kw.id)
        assert fetched is not None
        assert fetched.id == kw.id

    def test_get_missing_returns_none(self, store):
        assert store.get("nonexistent-id") is None

    def test_update_enabled(self, store):
        from src.news.models import KeywordUpdate
        kw = _create(store)
        updated = store.update(kw.id, KeywordUpdate(enabled=False))
        assert updated.enabled is False

    def test_update_interval(self, store):
        from src.news.models import KeywordUpdate
        kw = _create(store, interval=60)
        updated = store.update(kw.id, KeywordUpdate(fetch_interval_minutes=120))
        assert updated.fetch_interval_minutes == 120

    def test_delete_removes_keyword(self, store):
        kw = _create(store)
        assert store.delete(kw.id) is True
        assert store.get(kw.id) is None

    def test_delete_nonexistent_returns_false(self, store):
        assert store.delete("no-such-id") is False

    def test_term_exists(self, store):
        _create(store, "Politics")
        assert store.term_exists("Politics") is True
        assert store.term_exists("Economy") is False

    def test_term_exists_case_insensitive(self, store):
        _create(store, "politics")
        assert store.term_exists("POLITICS") is True

    def test_mark_fetched_updates_timestamp(self, store):
        kw = _create(store)
        assert kw.last_fetched_at is None
        store.mark_fetched(kw.id)
        updated = store.get(kw.id)
        assert updated.last_fetched_at is not None

    def test_mark_fetched_records_error(self, store):
        kw = _create(store)
        store.mark_fetched(kw.id, error="429 rate limit")
        updated = store.get(kw.id)
        assert updated.last_error == "429 rate limit"

    def test_mark_fetched_clears_error(self, store):
        kw = _create(store)
        store.mark_fetched(kw.id, error="oops")
        store.mark_fetched(kw.id, error=None)
        updated = store.get(kw.id)
        assert updated.last_error is None

    def test_get_due_returns_enabled_past_interval(self, store):
        import sqlite3
        kw = _create(store, interval=60)
        past = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("UPDATE keywords SET last_fetched_at=? WHERE id=?", (past, kw.id))
            conn.commit()
        due = store.get_due()
        assert any(k.id == kw.id for k in due)

    def test_get_due_excludes_disabled(self, store):
        from src.news.models import KeywordUpdate
        import sqlite3
        kw = _create(store, interval=60)
        past = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("UPDATE keywords SET last_fetched_at=? WHERE id=?", (past, kw.id))
            conn.commit()
        store.update(kw.id, KeywordUpdate(enabled=False))
        due = store.get_due()
        assert not any(k.id == kw.id for k in due)
