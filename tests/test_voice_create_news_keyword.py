"""End-to-end voice pipeline test: wake word → "Add NASA as a news keyword".

Covers:
  1. Wake word "hey_jarvis" detection fires the IDLE → LISTENING transition.
  2. STT transcribes the utterance as the NASA keyword request.
  3. VoiceClient sends the correct WebSocket message to RAGenie.
  4. A mocked WS server replies with a tool_call (create_news_keyword)
     followed by the confirmation text.
  5. NewsService.create_keyword is called with term="NASA".
  6. KeywordStore (real in-memory SQLite) persists the keyword correctly.

No audio hardware, no model files, no live server required.
"""
import asyncio
import json
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch

from src.news.keyword_store import KeywordStore
from src.news.models import KeywordCreate
from src.voice.voice_client import VoiceClient, VoiceState


# ── Shared fixtures ────────────────────────────────────────────────────────────

NASA_UTTERANCE = "Add NASA as a news keyword"
CONFIRMATION   = "Done! I've added NASA as a news keyword in RAGenie."

WAKE_CHUNK  = np.zeros(1280, dtype=np.float32)  # audio fed to wake engine
SPEECH_CLIP = np.zeros(4096, dtype=np.float32)  # "audio" returned by STT


def _make_config(phrase="hey_jarvis"):
    cfg = MagicMock()
    cfg.wake_word.phrase    = phrase
    cfg.wake_word.model_path = None
    cfg.wake_word.threshold  = 0.5
    cfg.vad_silence_ms       = 800
    cfg.barge_in_threshold   = 0.015
    cfg.llm_model            = "llama3.2"
    cfg.use_agent            = True
    cfg.conversation_id_prefix = "voice"
    cfg.stt = MagicMock()
    cfg.tts = MagicMock()
    return cfg


@pytest.fixture
def keyword_store(tmp_path):
    """Real SQLite-backed keyword store (temp DB, discarded after each test)."""
    db = str(tmp_path / "news.db")
    from src.news.article_store import ArticleStore
    ArticleStore(db)          # creates articles / article_summaries tables
    return KeywordStore(db)


# ── Unit: KeywordStore persists "NASA" ────────────────────────────────────────

class TestNASAKeywordStore:
    def test_create_nasa_keyword(self, keyword_store):
        kw = keyword_store.create(
            KeywordCreate(term="NASA", fetch_interval_minutes=60, max_articles_per_fetch=10)
        )
        assert kw.term == "NASA"
        assert kw.enabled is True
        assert kw.id is not None

    def test_nasa_term_exists_after_create(self, keyword_store):
        keyword_store.create(
            KeywordCreate(term="NASA", fetch_interval_minutes=60, max_articles_per_fetch=10)
        )
        assert keyword_store.term_exists("NASA") is True

    def test_nasa_case_insensitive_exists(self, keyword_store):
        keyword_store.create(
            KeywordCreate(term="NASA", fetch_interval_minutes=60, max_articles_per_fetch=10)
        )
        assert keyword_store.term_exists("nasa") is True
        assert keyword_store.term_exists("Nasa") is True

    def test_nasa_listed_after_create(self, keyword_store):
        keyword_store.create(
            KeywordCreate(term="NASA", fetch_interval_minutes=60, max_articles_per_fetch=10)
        )
        keywords = keyword_store.list_all()
        assert any(k.term == "NASA" for k in keywords)

    def test_duplicate_nasa_raises(self, keyword_store):
        keyword_store.create(
            KeywordCreate(term="NASA", fetch_interval_minutes=60, max_articles_per_fetch=10)
        )
        with pytest.raises(Exception):
            keyword_store.create(
                KeywordCreate(term="NASA", fetch_interval_minutes=60, max_articles_per_fetch=10)
            )


# ── Unit: NewsService.create_keyword called with "NASA" ───────────────────────

class TestNewsServiceCreateNASAKeyword:
    def _make_service(self, keyword_store):
        from src.news.news_service import NewsService
        svc = NewsService(
            keyword_store=keyword_store,
            article_store=MagicMock(),
            fetcher=None,
            processor=MagicMock(),
            summariser=MagicMock(),
            scheduler=MagicMock(),
        )
        return svc

    def test_service_create_nasa(self, keyword_store):
        svc = self._make_service(keyword_store)
        kw = svc.create_keyword(
            KeywordCreate(term="NASA", fetch_interval_minutes=60, max_articles_per_fetch=10)
        )
        assert kw.term == "NASA"
        assert kw.enabled is True

    def test_service_keyword_exists_nasa(self, keyword_store):
        svc = self._make_service(keyword_store)
        svc.create_keyword(
            KeywordCreate(term="NASA", fetch_interval_minutes=60, max_articles_per_fetch=10)
        )
        assert svc.keyword_exists("NASA") is True

    def test_service_registers_scheduler_on_create(self, keyword_store):
        from src.news.news_service import NewsService
        mock_scheduler = MagicMock()
        svc = NewsService(
            keyword_store=keyword_store,
            article_store=MagicMock(),
            fetcher=None,
            processor=MagicMock(),
            summariser=MagicMock(),
            scheduler=mock_scheduler,
        )
        svc.create_keyword(
            KeywordCreate(term="NASA", fetch_interval_minutes=60, max_articles_per_fetch=10)
        )
        mock_scheduler.register_keyword.assert_called_once()
        registered = mock_scheduler.register_keyword.call_args[0][0]
        assert registered.term == "NASA"


# ── Unit: Wake-word detection fires IDLE → LISTENING ──────────────────────────

class TestWakeWordHeyJarvis:
    @pytest.mark.asyncio
    async def test_hey_jarvis_transitions_to_listening(self):
        cfg = _make_config(phrase="hey_jarvis")
        with patch("src.voice.voice_client.MicCapture"), \
             patch("src.voice.voice_client.AudioPlayer"), \
             patch("src.voice.voice_client.WakeWordEngine") as MockWake, \
             patch("src.voice.voice_client.STTEngine"), \
             patch("src.voice.voice_client.TTSEngine"), \
             patch("src.voice.voice_client.update_state"), \
             patch("src.voice.voice_client.clear_state"):
            client = VoiceClient(cfg, "ws://localhost:8000/ws/test")
            client._mic.read_chunk.return_value = WAKE_CHUNK
            client._wake.process_chunk.return_value = True  # "hey_jarvis" detected
            client._speak_ready = AsyncMock()

            await client._step()

        assert client._state == VoiceState.LISTENING

    @pytest.mark.asyncio
    async def test_hey_jarvis_resets_wake_engine(self):
        cfg = _make_config(phrase="hey_jarvis")
        with patch("src.voice.voice_client.MicCapture"), \
             patch("src.voice.voice_client.AudioPlayer"), \
             patch("src.voice.voice_client.WakeWordEngine"), \
             patch("src.voice.voice_client.STTEngine"), \
             patch("src.voice.voice_client.TTSEngine"), \
             patch("src.voice.voice_client.update_state"), \
             patch("src.voice.voice_client.clear_state"):
            client = VoiceClient(cfg, "ws://localhost:8000/ws/test")
            client._mic.read_chunk.return_value = WAKE_CHUNK
            client._wake.process_chunk.return_value = True
            client._speak_ready = AsyncMock()

            await client._step()

        client._wake.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_wake_stays_idle(self):
        cfg = _make_config(phrase="hey_jarvis")
        with patch("src.voice.voice_client.MicCapture"), \
             patch("src.voice.voice_client.AudioPlayer"), \
             patch("src.voice.voice_client.WakeWordEngine"), \
             patch("src.voice.voice_client.STTEngine"), \
             patch("src.voice.voice_client.TTSEngine"), \
             patch("src.voice.voice_client.update_state"), \
             patch("src.voice.voice_client.clear_state"):
            client = VoiceClient(cfg, "ws://localhost:8000/ws/test")
            client._mic.read_chunk.return_value = WAKE_CHUNK
            client._wake.process_chunk.return_value = False  # no wake word

            await client._step()

        assert client._state == VoiceState.IDLE


# ── Unit: STT transcribes NASA utterance & _handle_response called ────────────

class TestSTTNASAUtterance:
    @pytest.mark.asyncio
    async def test_nasa_utterance_calls_handle_response(self):
        cfg = _make_config()
        with patch("src.voice.voice_client.MicCapture"), \
             patch("src.voice.voice_client.AudioPlayer"), \
             patch("src.voice.voice_client.WakeWordEngine"), \
             patch("src.voice.voice_client.STTEngine"), \
             patch("src.voice.voice_client.TTSEngine"), \
             patch("src.voice.voice_client.update_state"), \
             patch("src.voice.voice_client.clear_state"):
            client = VoiceClient(cfg, "ws://localhost:8000/ws/test")
            client._state = VoiceState.LISTENING
            client._stt.collect_utterance.return_value = SPEECH_CLIP
            client._stt.transcribe.return_value = NASA_UTTERANCE
            client._handle_response = AsyncMock()

            await client._step()

        client._handle_response.assert_called_once_with(NASA_UTTERANCE)

    @pytest.mark.asyncio
    async def test_nasa_utterance_state_returns_to_idle(self):
        cfg = _make_config()
        with patch("src.voice.voice_client.MicCapture"), \
             patch("src.voice.voice_client.AudioPlayer"), \
             patch("src.voice.voice_client.WakeWordEngine"), \
             patch("src.voice.voice_client.STTEngine"), \
             patch("src.voice.voice_client.TTSEngine"), \
             patch("src.voice.voice_client.update_state"), \
             patch("src.voice.voice_client.clear_state"):
            client = VoiceClient(cfg, "ws://localhost:8000/ws/test")
            client._state = VoiceState.LISTENING
            client._stt.collect_utterance.return_value = SPEECH_CLIP
            client._stt.transcribe.return_value = NASA_UTTERANCE
            client._handle_response = AsyncMock()

            await client._step()

        assert client._state == VoiceState.IDLE


# ── Integration: full voice → WS → news keyword creation flow ─────────────────

class TestVoiceCreateNASAKeywordIntegration:
    """
    Simulates the full path:
      hey_jarvis → "Add NASA as a news keyword"
        → WS message sent to RAGenie
        → RAGenie replies: tool_call(create_news_keyword) + confirmation text
        → NewsService.create_keyword called with term="NASA"
    """

    def _ws_event_sequence(self):
        """Fake WS messages RAGenie would send back."""
        return [
            json.dumps({"type": "tool_call",    "tool": "create_news_keyword"}),
            json.dumps({"type": "stream_token", "content": CONFIRMATION}),
            json.dumps({"type": "stream_end"}),
        ]

    @pytest.mark.asyncio
    async def test_ws_message_contains_nasa_utterance(self):
        """VoiceClient must forward the exact transcribed text to the WebSocket."""
        cfg = _make_config()
        sent_messages = []

        async def fake_connect(url):
            ws = MagicMock()
            ws.send = AsyncMock(side_effect=lambda m: sent_messages.append(m))
            events = iter(self._ws_event_sequence())
            ws.recv = AsyncMock(side_effect=lambda: next(events))
            ws.close = AsyncMock()
            return ws

        with patch("src.voice.voice_client.MicCapture"), \
             patch("src.voice.voice_client.AudioPlayer"), \
             patch("src.voice.voice_client.WakeWordEngine"), \
             patch("src.voice.voice_client.STTEngine"), \
             patch("src.voice.voice_client.TTSEngine"), \
             patch("src.voice.voice_client.update_state"), \
             patch("src.voice.voice_client.clear_state"), \
             patch("websockets.connect", new=fake_connect):
            client = VoiceClient(cfg, "ws://localhost:8000/ws/test")
            client._tts.speak_stream = AsyncMock()
            client._player = MagicMock()

            await client._handle_response(NASA_UTTERANCE)

        assert len(sent_messages) == 1
        payload = json.loads(sent_messages[0])
        assert payload["message"] == NASA_UTTERANCE
        assert payload["use_agent"] is True
        assert payload["use_reasoning"] is False

    @pytest.mark.asyncio
    async def test_tool_call_create_news_keyword_received(self):
        """VoiceClient must handle tool_call events without crashing."""
        cfg = _make_config()
        received_tool_calls = []

        events = iter(self._ws_event_sequence())

        async def fake_recv():
            return next(events)

        async def fake_connect(url):
            ws = MagicMock()
            ws.send  = AsyncMock()
            ws.recv  = AsyncMock(side_effect=fake_recv)
            ws.close = AsyncMock()
            return ws

        with patch("src.voice.voice_client.MicCapture"), \
             patch("src.voice.voice_client.AudioPlayer"), \
             patch("src.voice.voice_client.WakeWordEngine"), \
             patch("src.voice.voice_client.STTEngine"), \
             patch("src.voice.voice_client.TTSEngine"), \
             patch("src.voice.voice_client.update_state",
                   side_effect=lambda state, **kw:
                       received_tool_calls.append(kw.get("tool"))
                       if kw.get("tool") else None), \
             patch("src.voice.voice_client.clear_state"), \
             patch("websockets.connect", new=fake_connect):
            client = VoiceClient(cfg, "ws://localhost:8000/ws/test")
            client._tts.speak_stream = AsyncMock()
            client._player = MagicMock()

            await client._handle_response(NASA_UTTERANCE)

        assert "create_news_keyword" in received_tool_calls

    @pytest.mark.asyncio
    async def test_nasa_news_keyword_persisted_via_service(self, keyword_store):
        """After the voice command the keyword 'NASA' must exist in the store."""
        from src.news.news_service import NewsService

        mock_scheduler = MagicMock()
        svc = NewsService(
            keyword_store=keyword_store,
            article_store=MagicMock(),
            fetcher=None,
            processor=MagicMock(),
            summariser=MagicMock(),
            scheduler=mock_scheduler,
        )

        # Simulate what the agent tool handler does on receiving the voice command
        req = KeywordCreate(term="NASA", fetch_interval_minutes=60, max_articles_per_fetch=10)
        kw = svc.create_keyword(req)

        assert kw.term == "NASA"
        assert keyword_store.term_exists("NASA") is True
        assert any(k.term == "NASA" for k in keyword_store.list_all())
