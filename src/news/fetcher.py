"""News article fetcher — Google News RSS (no API key, full language support).

Uses only Python stdlib: urllib + xml.etree.ElementTree.

Google News RSS URL format:
  https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}

Time filtering is done via Google's ``when:`` query operator so results are
always fresh (e.g. ``when:1d`` = past 24 hours).
"""
import re
import ssl
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Tuple

from ..core.logging_config import get_logger
from .models import RawArticle

logger = get_logger(__name__)

_RETRY_BACKOFF = [3, 8, 15]
_GNEWS_BASE = "https://news.google.com/rss/search"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; RAGenie-NewsBot/1.0; "
        "+https://github.com/ratulsarkar/RAGenie)"
    )
}

# region code → (hl, gl, ceid)
# region is the same string used in config.yaml → news.region
# All Indian languages are natively supported by Google News RSS.
REGION_CODES: dict[str, Tuple[str, str, str]] = {
    # Worldwide (default)
    "wt-wt":  ("en",    "US", "US:en"),
    # ---------- Indian languages ----------
    "in-en":  ("en-IN", "IN", "IN:en"),   # English (India)
    "in-hi":  ("hi",    "IN", "IN:hi"),   # Hindi        हिन्दी
    "in-bn":  ("bn",    "IN", "IN:bn"),   # Bengali      বাংলা
    "in-te":  ("te",    "IN", "IN:te"),   # Telugu       తెలుగు
    "in-mr":  ("mr",    "IN", "IN:mr"),   # Marathi      मराठी
    "in-ta":  ("ta",    "IN", "IN:ta"),   # Tamil        தமிழ்
    "in-gu":  ("gu",    "IN", "IN:gu"),   # Gujarati     ગુજરાતી
    "in-kn":  ("kn",    "IN", "IN:kn"),   # Kannada      ಕನ್ನಡ
    "in-ml":  ("ml",    "IN", "IN:ml"),   # Malayalam    മലയാളം
    "in-pa":  ("pa",    "IN", "IN:pa"),   # Punjabi      ਪੰਜਾਬੀ
    "in-or":  ("or",    "IN", "IN:or"),   # Odia         ଓଡ଼ିଆ
    "in-ur":  ("ur",    "IN", "IN:ur"),   # Urdu         اردو
    # ---------- Other major regions ----------
    "us-en":  ("en",    "US", "US:en"),
    "gb-en":  ("en",    "GB", "GB:en"),
    "de-de":  ("de",    "DE", "DE:de"),
    "fr-fr":  ("fr",    "FR", "FR:fr"),
    "jp-jp":  ("ja",    "JP", "JP:ja"),
    "xa-ar":  ("ar",    "SA", "SA:ar"),
}

def _ssl_context() -> ssl.SSLContext:
    """Return an SSL context with verified certs (uses certifi on macOS)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


_SSL_CTX = _ssl_context()

_HTML_TAG = re.compile(r"<[^>]+>")
_HTML_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
}


def _strip_html(text: str) -> str:
    text = _HTML_TAG.sub(" ", text)
    for ent, ch in _HTML_ENTITIES.items():
        text = text.replace(ent, ch)
    return " ".join(text.split())


def _when_param(from_date: Optional[datetime]) -> str:
    """Map from_date → Google News ``when:`` operator token."""
    if from_date is None:
        return "when:1d"
    now = datetime.now(timezone.utc)
    aware_from = from_date if from_date.tzinfo is not None else from_date.replace(tzinfo=timezone.utc)
    age_h = (now - aware_from).total_seconds() / 3600
    if age_h <= 1:
        return "when:1h"
    if age_h <= 6:
        return "when:6h"
    if age_h <= 24:
        return "when:1d"
    if age_h <= 72:
        return "when:3d"
    return "when:7d"


def _build_url(keyword: str, region: str, from_date: Optional[datetime]) -> str:
    hl, gl, ceid = REGION_CODES.get(region, REGION_CODES["wt-wt"])
    when = _when_param(from_date)
    q = f"{keyword} {when}"
    params = urllib.parse.urlencode({"q": q, "hl": hl, "gl": gl, "ceid": ceid})
    return f"{_GNEWS_BASE}?{params}"


class NewsFetcher:
    """Fetches news via Google News RSS — no API key, any language/script."""

    def __init__(self, region: str = "wt-wt"):
        self._region = region if region in REGION_CODES else "wt-wt"

    def fetch(
        self,
        keyword: str,
        page_size: int = 10,
        max_pages: int = 1,
        from_date: Optional[datetime] = None,
    ) -> List[RawArticle]:
        limit = min(page_size * max_pages, 100)
        url = _build_url(keyword, self._region, from_date)

        for attempt, wait in enumerate([0] + _RETRY_BACKOFF):
            if wait:
                logger.debug(f"Retrying in {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
            try:
                req = urllib.request.Request(url, headers=_HEADERS)
                with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
                    xml_bytes = resp.read()
                articles = self._parse_feed(xml_bytes, limit)
                logger.info(
                    f"Google News: {len(articles)} articles for '{keyword}' "
                    f"(region={self._region})"
                )
                return articles
            except Exception as e:
                logger.warning(f"Google News fetch attempt {attempt + 1} failed: {e}")
                if attempt >= len(_RETRY_BACKOFF):
                    logger.error(f"All attempts exhausted for '{keyword}'")
                    return []
        return []

    @staticmethod
    def _parse_feed(xml_bytes: bytes, limit: int) -> List[RawArticle]:
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            logger.error(f"RSS XML parse error: {e}")
            return []

        ns = {"media": "http://search.yahoo.com/mrss/"}
        channel = root.find("channel")
        if channel is None:
            return []

        articles: List[RawArticle] = []
        for item in channel.findall("item")[:limit]:
            title_raw = item.findtext("title") or ""
            link = item.findtext("link") or ""
            pub_raw = item.findtext("pubDate") or ""
            desc_raw = item.findtext("description") or ""

            source_el = item.find("source")
            source = source_el.text.strip() if source_el is not None and source_el.text else ""

            title = _strip_html(title_raw)
            # Google often appends " - Source Name" to the title — strip it
            if source and title.endswith(f" - {source}"):
                title = title[: -(len(source) + 3)].strip()

            content = _strip_html(desc_raw)

            pub: Optional[datetime] = None
            if pub_raw:
                try:
                    pub = parsedate_to_datetime(pub_raw).replace(tzinfo=None)
                except Exception:
                    pass

            if title and link:
                articles.append(
                    RawArticle(
                        title=title,
                        content=content,
                        url=link,
                        source=source,
                        published_at=pub,
                    )
                )
        return articles
