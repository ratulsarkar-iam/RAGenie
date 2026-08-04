"""Pydantic models for the News Aggregator feature."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class KeywordCreate(BaseModel):
    term: str = Field(..., min_length=1, max_length=200)
    fetch_interval_minutes: int = Field(default=60, ge=5, le=1440)
    max_articles_per_fetch: int = Field(default=10, ge=1, le=100)


class Keyword(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    term: str
    enabled: bool = True
    fetch_interval_minutes: int = 60
    max_articles_per_fetch: int = 10
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_fetched_at: Optional[datetime] = None
    article_count: int = 0
    last_error: Optional[str] = None


class KeywordUpdate(BaseModel):
    term: Optional[str] = Field(default=None, min_length=1, max_length=200)
    enabled: Optional[bool] = None
    fetch_interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)
    max_articles_per_fetch: Optional[int] = Field(default=None, ge=1, le=100)


class RawArticle(BaseModel):
    title: str
    content: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    image_url: Optional[str] = None


class Article(BaseModel):
    id: str
    keyword_id: str
    title: str
    content: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_summarised: bool = False
    rag_doc_id: Optional[str] = None
    image_url: Optional[str] = None


class ArticleSummary(BaseModel):
    article_id: str
    summary: str
    model: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ArticleWithSummary(BaseModel):
    id: str
    keyword_id: str
    title: str
    content: str
    url: str
    source: str
    published_at: Optional[datetime] = None
    fetched_at: datetime
    is_summarised: bool
    rag_doc_id: Optional[str] = None
    image_url: Optional[str] = None
    summary: Optional[str] = None
    summary_model: Optional[str] = None
