"""REST API routes for the News Aggregator feature."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..news.models import Keyword, KeywordCreate, KeywordUpdate, ArticleWithSummary
from ..news.translation_config import TRANSLATION_LANGUAGES
from ..core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["news"])


def _svc():
    from .app import app_state  # deferred import to avoid circular dependency
    svc = app_state.get("news_service")
    if svc is None:
        raise HTTPException(status_code=503, detail="News service not initialised or disabled")
    return svc


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
async def list_keywords():
    return _svc().list_keywords()


class SuggestRequest(BaseModel):
    description: str


@router.post("/api/keywords/suggest")
async def suggest_keyword(body: SuggestRequest):
    """Use the LLM to turn a natural-language description into an optimal news search term."""
    if not body.description.strip():
        raise HTTPException(status_code=400, detail="Description is required")
    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(
        None, _svc().suggest_keyword, body.description
    )
    return result


@router.post("/api/keywords", response_model=Keyword, status_code=201)
async def create_keyword(body: KeywordCreate):
    svc = _svc()
    if svc.keyword_exists(body.term):
        raise HTTPException(status_code=409, detail=f"Keyword '{body.term}' already exists")
    return svc.create_keyword(body)


@router.patch("/api/keywords/{keyword_id}", response_model=Keyword)
async def update_keyword(keyword_id: str, body: KeywordUpdate):
    svc = _svc()
    kw = svc.update_keyword(keyword_id, body)
    if kw is None:
        raise HTTPException(status_code=404, detail="Keyword not found")
    return kw


@router.delete("/api/keywords/{keyword_id}")
async def delete_keyword(keyword_id: str):
    svc = _svc()
    if not svc.delete_keyword(keyword_id):
        raise HTTPException(status_code=404, detail="Keyword not found")
    return {"status": "deleted", "id": keyword_id}


@router.post("/api/keywords/{keyword_id}/fetch-now", status_code=202)
async def fetch_now(keyword_id: str):
    svc = _svc()
    if svc.get_keyword(keyword_id) is None:
        raise HTTPException(status_code=404, detail="Keyword not found")
    import asyncio
    asyncio.get_event_loop().run_in_executor(None, svc.fetch_now, keyword_id)
    return {"status": "fetch_enqueued", "keyword_id": keyword_id}


# ---------- Articles ----------

@router.get("/api/news", response_model=List[ArticleWithSummary])
async def list_articles(
    keyword_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    return _svc().get_articles(keyword_id=keyword_id, page=page, limit=limit)


@router.get("/api/news/{article_id}", response_model=ArticleWithSummary)
async def get_article(article_id: str):
    article = _svc().get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("/api/news/{article_id}/summarize", response_model=ArticleWithSummary)
async def resummarise_article(article_id: str):
    import asyncio
    svc = _svc()
    article = await asyncio.get_event_loop().run_in_executor(None, svc.resummarise, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


class TranslateRequest(BaseModel):
    language_code: str


@router.post("/api/news/{article_id}/translate")
async def translate_article_summary(article_id: str, body: TranslateRequest):
    """Translate an article's summary to the target language."""
    import asyncio
    svc = _svc()
    article = svc.get_article(article_id)
    if not article or not article.summary:
        raise HTTPException(status_code=404, detail="Article or summary not found")
    
    # Find language name from code
    lang_name = next((l["name"] for l in TRANSLATION_LANGUAGES if l["code"] == body.language_code), body.language_code)
    
    translated = await asyncio.get_event_loop().run_in_executor(
        None, svc._summariser.translate_summary, article.summary, lang_name
    )
    return {"translated_summary": translated, "language_code": body.language_code}


@router.delete("/api/news/{article_id}")
async def delete_article(article_id: str):
    if not _svc().delete_article(article_id):
        raise HTTPException(status_code=404, detail="Article not found")
    return {"status": "deleted", "id": article_id}
