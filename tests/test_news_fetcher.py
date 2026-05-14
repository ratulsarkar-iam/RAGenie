"""Unit tests for NewsFetcher (Google News RSS) — mocks urllib.request.urlopen."""
import xml.etree.ElementTree as ET
from datetime import datetime
from unittest.mock import patch, MagicMock
from io import BytesIO

import pytest

from src.news.fetcher import NewsFetcher, _build_url, _when_param, REGION_CODES


def _make_rss(items: list[dict]) -> bytes:
    """Build a minimal Google News RSS XML payload."""
    root = ET.Element("rss")
    root.set("version", "2.0")
    channel = ET.SubElement(root, "channel")
    for item_data in items:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = item_data.get("title", "Test Title")
        ET.SubElement(item, "link").text = item_data.get("link", "https://example.com/article")
        ET.SubElement(item, "pubDate").text = item_data.get("pubDate", "Sun, 11 May 2025 10:00:00 GMT")
        ET.SubElement(item, "description").text = item_data.get("description", "A brief snippet.")
        if "source" in item_data:
            src_el = ET.SubElement(item, "source")
            src_el.text = item_data["source"]
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _mock_urlopen(xml_bytes: bytes):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=xml_bytes)))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TestBuildUrl:
    def test_default_region(self):
        url = _build_url("test", "wt-wt", None)
        assert "hl=en" in url
        assert "gl=US" in url
        assert "when%3A1d" in url or "when:1d" in url

    def test_hindi_region(self):
        url = _build_url("test", "in-hi", None)
        assert "hl=hi" in url
        assert "gl=IN" in url

    def test_bengali_region(self):
        url = _build_url("test", "in-bn", None)
        assert "hl=bn" in url

    def test_unknown_region_falls_back_to_default(self):
        url = _build_url("test", "xx-xx", None)
        assert "hl=en" in url

    def test_when_param_1d_default(self):
        assert _when_param(None) == "when:1d"

    def test_when_param_recent(self):
        from datetime import timedelta
        recent = datetime.utcnow() - timedelta(hours=2)
        assert _when_param(recent) == "when:6h"

    def test_when_param_old(self):
        from datetime import timedelta
        old = datetime.utcnow() - timedelta(days=5)
        assert _when_param(old) == "when:7d"


class TestNewsFetcher:
    def test_successful_fetch_returns_articles(self):
        xml = _make_rss([
            {"title": "West Bengal Elections", "link": "https://example.com/1", "source": "BBC"},
            {"title": "Bengal Economy",        "link": "https://example.com/2", "source": "Reuters"},
        ])
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(xml)):
            fetcher = NewsFetcher(region="in-en")
            articles = fetcher.fetch("West Bengal")
        assert len(articles) == 2
        assert articles[0].title == "West Bengal Elections"
        assert articles[0].source == "BBC"

    def test_empty_rss_returns_empty_list(self):
        xml = _make_rss([])
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(xml)):
            fetcher = NewsFetcher()
            articles = fetcher.fetch("nothing")
        assert articles == []

    def test_item_without_link_is_skipped(self):
        xml = _make_rss([{"title": "No link article", "link": ""}])
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(xml)):
            fetcher = NewsFetcher()
            articles = fetcher.fetch("test")
        assert articles == []

    def test_malformed_xml_returns_empty_list(self):
        bad_xml = b"<this is not xml at all!!!"
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(bad_xml)):
            fetcher = NewsFetcher()
            articles = fetcher.fetch("test")
        assert articles == []

    def test_network_error_returns_empty_after_retries(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            with patch("time.sleep"):
                fetcher = NewsFetcher()
                articles = fetcher.fetch("test")
        assert articles == []

    def test_limit_applied(self):
        items = [{"title": f"Article {i}", "link": f"https://example.com/{i}"} for i in range(20)]
        xml = _make_rss(items)
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(xml)):
            fetcher = NewsFetcher()
            articles = fetcher.fetch("test", page_size=5, max_pages=1)
        assert len(articles) == 5

    def test_source_suffix_stripped_from_title(self):
        xml = _make_rss([{
            "title": "Bengal news headline - BBC",
            "link": "https://example.com/x",
            "source": "BBC",
        }])
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(xml)):
            fetcher = NewsFetcher()
            articles = fetcher.fetch("Bengal")
        assert articles[0].title == "Bengal news headline"

    def test_published_at_parsed(self):
        xml = _make_rss([{
            "title": "Date test",
            "link": "https://example.com/date",
            "pubDate": "Mon, 11 May 2026 08:30:00 GMT",
        }])
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(xml)):
            fetcher = NewsFetcher()
            articles = fetcher.fetch("test")
        assert articles[0].published_at is not None
        assert articles[0].published_at.year == 2026

    def test_unknown_region_coerced_to_default(self):
        fetcher = NewsFetcher(region="zz-zz")
        assert fetcher._region == "wt-wt"

    def test_all_indian_regions_in_region_codes(self):
        indian = ["in-en", "in-hi", "in-bn", "in-te", "in-mr", "in-ta",
                  "in-gu", "in-kn", "in-ml", "in-pa", "in-or", "in-ur"]
        for code in indian:
            assert code in REGION_CODES, f"Missing region: {code}"
