"""Integration tests for News API routes — uses FastAPI TestClient with mocked NewsService."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime


@pytest.fixture
def mock_service():
    svc = MagicMock()
    svc.list_keywords.return_value = []
    svc.keyword_exists.return_value = False
    return svc


@pytest.fixture
def client(mock_service):
    from fastapi import FastAPI
    from src.api.news_routes import router
    import src.api.app as app_module

    app = FastAPI()
    app.include_router(router)
    app_module.app_state["news_service"] = mock_service
    yield TestClient(app)
    app_module.app_state.pop("news_service", None)


@pytest.fixture
def client_no_service():
    from fastapi import FastAPI
    from src.api.news_routes import router
    import src.api.app as app_module

    app = FastAPI()
    app.include_router(router)
    app_module.app_state.pop("news_service", None)
    yield TestClient(app)


def _kw_dict(**overrides):
    base = {
        "id": "kw-1",
        "term": "West Bengal",
        "enabled": True,
        "fetch_interval_minutes": 60,
        "max_articles_per_fetch": 10,
        "created_at": datetime.utcnow().isoformat(),
        "last_fetched_at": None,
        "article_count": 0,
        "last_error": None,
    }
    base.update(overrides)
    return base


class TestKeywordEndpoints:
    def test_list_keywords_empty(self, client, mock_service):
        resp = client.get("/api/keywords")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_keywords_returns_items(self, client, mock_service):
        mock_service.list_keywords.return_value = [MagicMock(**_kw_dict())]
        # Use dict return for simpler serialisation
        from src.news.models import Keyword
        mock_service.list_keywords.return_value = [Keyword(**_kw_dict())]
        resp = client.get("/api/keywords")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_create_keyword_201(self, client, mock_service):
        from src.news.models import Keyword
        mock_service.create_keyword.return_value = Keyword(**_kw_dict())
        resp = client.post("/api/keywords", json={"term": "West Bengal"})
        assert resp.status_code == 201
        assert resp.json()["term"] == "West Bengal"

    def test_create_keyword_409_on_duplicate(self, client, mock_service):
        mock_service.keyword_exists.return_value = True
        resp = client.post("/api/keywords", json={"term": "West Bengal"})
        assert resp.status_code == 409

    def test_create_keyword_422_on_empty_term(self, client, mock_service):
        resp = client.post("/api/keywords", json={"term": ""})
        assert resp.status_code == 422

    def test_patch_keyword_200(self, client, mock_service):
        from src.news.models import Keyword
        mock_service.update_keyword.return_value = Keyword(**_kw_dict(enabled=False))
        resp = client.patch("/api/keywords/kw-1", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_patch_keyword_404(self, client, mock_service):
        mock_service.update_keyword.return_value = None
        resp = client.patch("/api/keywords/bad-id", json={"enabled": False})
        assert resp.status_code == 404

    def test_delete_keyword_200(self, client, mock_service):
        mock_service.delete_keyword.return_value = True
        resp = client.delete("/api/keywords/kw-1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

    def test_delete_keyword_404(self, client, mock_service):
        mock_service.delete_keyword.return_value = False
        resp = client.delete("/api/keywords/bad-id")
        assert resp.status_code == 404

    def test_fetch_now_202(self, client, mock_service):
        from src.news.models import Keyword
        mock_service.get_keyword.return_value = Keyword(**_kw_dict())
        resp = client.post("/api/keywords/kw-1/fetch-now")
        assert resp.status_code == 202
        assert resp.json()["status"] == "fetch_enqueued"

    def test_fetch_now_404(self, client, mock_service):
        mock_service.get_keyword.return_value = None
        resp = client.post("/api/keywords/bad-id/fetch-now")
        assert resp.status_code == 404


class TestArticleEndpoints:
    def test_list_articles_200(self, client, mock_service):
        mock_service.get_articles.return_value = []
        resp = client.get("/api/news")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_article_404(self, client, mock_service):
        mock_service.get_article.return_value = None
        resp = client.get("/api/news/no-such-id")
        assert resp.status_code == 404

    def test_delete_article_404(self, client, mock_service):
        mock_service.delete_article.return_value = False
        resp = client.delete("/api/news/bad-id")
        assert resp.status_code == 404

    def test_delete_article_200(self, client, mock_service):
        mock_service.delete_article.return_value = True
        resp = client.delete("/api/news/art-1")
        assert resp.status_code == 200

    def test_resummarise_404(self, client, mock_service):
        mock_service.resummarise.return_value = None
        resp = client.post("/api/news/bad-id/summarize")
        assert resp.status_code == 404


class TestServiceDisabled:
    def test_returns_503_when_no_service(self, client_no_service):
        resp = client_no_service.get("/api/keywords")
        assert resp.status_code == 503

    def test_news_status_disabled(self, client_no_service):
        resp = client_no_service.get("/api/news/status")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False
