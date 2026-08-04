"""REST API routes for the News Aggregator feature — scoped per user."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..news.models import Keyword, KeywordCreate, KeywordUpdate, ArticleWithSummary
from ..news.translation_config import TRANSLATION_LANGUAGES
from ..auth.dependencies import require_auth
from ..auth.models import User
from ..core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["news"])


def _svc():
    from .app import app_state  # deferred import to avoid circular dependency
    svc = app_state.get("news_service")
    if svc is None:
        raise HTTPException(status_code=503, detail="News service not initialised or disabled")
    return svc


def _log_activity(user_id: str, event_type: str, description: str, metadata: Optional[dict] = None) -> None:
    from .app import app_state
    activity_logger = app_state.get("activity_logger")
    if activity_logger:
        activity_logger.log(user_id, event_type, description, metadata)


def _owned_keyword_or_404(svc, keyword_id: str, user_id: str) -> Keyword:
    kw = svc.get_keyword(keyword_id)
    if kw is None or kw.user_id != user_id:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return kw


# ---------- Status ----------

@router.get("/api/news/status")
async def news_status():
    """Returns whether the news module is enabled."""
    from .app import app_state
    return {"enabled": app_state.get("news_service") is not None}


@router.get("/api/news/translation-languages")
async def get_translation_languages():
    """Returns the list of available translation languages."""
    return {"languages": TRANSLATION_LANGUAGES}


# ---------- Keywords ----------

@router.get("/api/keywords", response_model=List[Keyword])
async def list_keywords(current_user: User = Depends(require_auth)):
    return _svc().list_keywords(current_user.id)


class SuggestRequest(BaseModel):
    description: str


@router.post("/api/keywords/suggest")
async def suggest_keyword(body: SuggestRequest, current_user: User = Depends(require_auth)):
    """Use the LLM to turn a natural-language description into an optimal news search term."""
    if not body.description.strip():
        raise HTTPException(status_code=400, detail="Description is required")
    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(
        None, _svc().suggest_keyword, body.description
    )
    return result


@router.post("/api/keywords", response_model=Keyword, status_code=201)
async def create_keyword(body: KeywordCreate, current_user: User = Depends(require_auth)):
    svc = _svc()
    if svc.keyword_exists(current_user.id, body.term):
        raise HTTPException(status_code=409, detail=f"Keyword '{body.term}' already exists")
    kw = svc.create_keyword(current_user.id, body)
    _log_activity(current_user.id, "keyword_created", f"Created keyword '{kw.term}'", {"keyword_id": kw.id})
    return kw


@router.patch("/api/keywords/{keyword_id}", response_model=Keyword)
async def update_keyword(keyword_id: str, body: KeywordUpdate, current_user: User = Depends(require_auth)):
    svc = _svc()
    _owned_keyword_or_404(svc, keyword_id, current_user.id)
    kw = svc.update_keyword(keyword_id, body)
    if kw is None:
        raise HTTPException(status_code=404, detail="Keyword not found")
    _log_activity(current_user.id, "keyword_updated", f"Updated keyword '{kw.term}'", {"keyword_id": kw.id})
    return kw


@router.delete("/api/keywords/{keyword_id}")
async def delete_keyword(keyword_id: str, current_user: User = Depends(require_auth)):
    svc = _svc()
    kw = _owned_keyword_or_404(svc, keyword_id, current_user.id)
    if not svc.delete_keyword(keyword_id):
        raise HTTPException(status_code=404, detail="Keyword not found")
    _log_activity(current_user.id, "keyword_deleted", f"Deleted keyword '{kw.term}'", {"keyword_id": keyword_id})
    return {"status": "deleted", "id": keyword_id}


@router.post("/api/keywords/{keyword_id}/fetch-now", status_code=202)
async def fetch_now(keyword_id: str, current_user: User = Depends(require_auth)):
    svc = _svc()
    kw = _owned_keyword_or_404(svc, keyword_id, current_user.id)
    import asyncio
    asyncio.get_event_loop().run_in_executor(None, svc.fetch_now, keyword_id)
    _log_activity(current_user.id, "news_fetch_now", f"Requested fetch-now for '{kw.term}'", {"keyword_id": keyword_id})
    return {"status": "fetch_enqueued", "keyword_id": keyword_id}


# ---------- Articles ----------

@router.get("/api/news", response_model=List[ArticleWithSummary])
async def list_articles(
    keyword_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_auth),
):
    svc = _svc()
    if keyword_id:
        _owned_keyword_or_404(svc, keyword_id, current_user.id)
        _log_activity(current_user.id, "news_search", f"Viewed articles for keyword_id={keyword_id}", {"keyword_id": keyword_id})
        return svc.get_articles(keyword_id=keyword_id, page=page, limit=limit)

    # No keyword_id given — constrain to the current user's own keyword IDs to avoid leaking others' articles.
    owned_ids = {kw.id for kw in svc.list_keywords(current_user.id)}
    if not owned_ids:
        return []
    all_articles = svc.get_articles(keyword_id=None, page=page, limit=limit)
    filtered = [a for a in all_articles if a.keyword_id in owned_ids]
    _log_activity(current_user.id, "news_search", "Viewed news feed (all own keywords)")
    return filtered


@router.get("/api/news/{article_id}", response_model=ArticleWithSummary)
async def get_article(article_id: str, current_user: User = Depends(require_auth)):
    svc = _svc()
    article = svc.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    _owned_keyword_or_404(svc, article.keyword_id, current_user.id)
    return article


@router.post("/api/news/{article_id}/summarize", response_model=ArticleWithSummary)
async def resummarise_article(article_id: str, current_user: User = Depends(require_auth)):
    import asyncio
    svc = _svc()
    existing = svc.get_article(article_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Article not found")
    _owned_keyword_or_404(svc, existing.keyword_id, current_user.id)
    article = await asyncio.get_event_loop().run_in_executor(None, svc.resummarise, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


class TranslateRequest(BaseModel):
    language_code: str


@router.post("/api/news/{article_id}/translate")
async def translate_article_summary(article_id: str, body: TranslateRequest, current_user: User = Depends(require_auth)):
    """Translate an article's summary to the target language."""
    import asyncio
    svc = _svc()
    article = svc.get_article(article_id)
    if not article or not article.summary:
        raise HTTPException(status_code=404, detail="Article or summary not found")
    _owned_keyword_or_404(svc, article.keyword_id, current_user.id)

    # Find language name from code
    lang_name = next((l["name"] for l in TRANSLATION_LANGUAGES if l["code"] == body.language_code), body.language_code)

    translated = await asyncio.get_event_loop().run_in_executor(
        None, svc._summariser.translate_summary, article.summary, lang_name
    )
    return {"translated_summary": translated, "language_code": body.language_code}


@router.delete("/api/news/{article_id}")
async def delete_article(article_id: str, current_user: User = Depends(require_auth)):
    svc = _svc()
    article = svc.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    _owned_keyword_or_404(svc, article.keyword_id, current_user.id)
    if not svc.delete_article(article_id):
        raise HTTPException(status_code=404, detail="Article not found")
    return {"status": "deleted", "id": article_id}
