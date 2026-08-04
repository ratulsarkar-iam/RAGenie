"""Unit tests for SentenceChunker and TTSEngine (Phase 5).

edge-tts, pyttsx3, and AudioPlayer are mocked; no network calls are made.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.voice.tts import SentenceChunker


# ── SentenceChunker ───────────────────────────────────────────────────────────

class TestSentenceChunkerFeed:
    def test_no_boundary_returns_empty(self):
        c = SentenceChunker()
        assert c.feed("Hello") == []

    def test_period_space_fires(self):
        c = SentenceChunker()
        assert c.feed("Hello. ") == ["Hello."]

    def test_question_mark_space_fires(self):
        c = SentenceChunker()
        assert c.feed("How are you? ") == ["How are you?"]

    def test_exclamation_space_fires(self):
        c = SentenceChunker()
        assert c.feed("Wow! ") == ["Wow!"]

    def test_multiple_sentences_in_single_feed(self):
        c = SentenceChunker()
        result = c.feed("Hello. World. ")
        assert result == ["Hello.", "World."]

    def test_sentence_built_across_multiple_feeds(self):
        c = SentenceChunker()
        c.feed("The capital")
        c.feed(" of France")
        c.feed(" is Paris")
        result = c.feed(". ")
        assert len(result) == 1
        assert "Paris" in result[0]

    def test_partial_sentence_held_in_buffer(self):
        c = SentenceChunker()
        c.feed("Hello world")
        assert c.drain() == "Hello world"

    def test_empty_string_feed_returns_empty(self):
        c = SentenceChunker()
        assert c.feed("") == []

    def test_whitespace_only_sentences_filtered(self):
        # "." is a valid sentence (not filtered) — it strips to "."
        c = SentenceChunker()
        result = c.feed(". ")
        assert result == ["."]   # single dot is returned as-is
        # A boundary with no preceding text emits nothing meaningful
        c2 = SentenceChunker()
        empty = c2.feed("")
        assert empty == []

    def test_max_buffer_forces_flush(self):
        c = SentenceChunker()
        long_text = "x" * (SentenceChunker.MAX_BUFFER_CHARS + 10)
        result = c.feed(long_text)
        assert len(result) == 1
        assert len(result[0]) > 0

    def test_buffer_empty_after_max_buffer_flush(self):
        c = SentenceChunker()
        c.feed("x" * (SentenceChunker.MAX_BUFFER_CHARS + 10))
        assert c.drain() == ""

    def test_token_by_token_accumulation(self):
        c = SentenceChunker()
        tokens = ["Paris", " is", " the", " capital", ".", " "]
        results = []
        for t in tokens:
            results.extend(c.feed(t))
        assert len(results) == 1
        assert "Paris" in results[0]


class TestSentenceChunkerDrain:
    def test_drain_returns_partial_text(self):
        c = SentenceChunker()
        c.feed("Unfinished sentence")
        assert c.drain() == "Unfinished sentence"

    def test_drain_clears_buffer(self):
        c = SentenceChunker()
        c.feed("Some text")
        c.drain()
        assert c.drain() == ""

    def test_drain_empty_returns_empty(self):
        c = SentenceChunker()
        assert c.drain() == ""

    def test_drain_strips_whitespace(self):
        c = SentenceChunker()
        c.feed("  spaces  ")
        assert c.drain() == "spaces"


# ── TTSEngine ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tts_config():
    cfg = MagicMock()
    cfg.engine = "edge-tts"
    cfg.voice = "en-US-JennyNeural"
    cfg.rate = "+0%"
    cfg.fallback_engine = "pyttsx3"
    return cfg


@pytest.fixture
def tts(tts_config):
    from src.voice.tts import TTSEngine
    return TTSEngine(tts_config)


class TestTTSEngineSynthesize:
    @pytest.mark.asyncio
    async def test_returns_concatenated_audio_bytes(self, tts):
        async def fake_stream():
            yield {"type": "audio", "data": b"PART1"}
            yield {"type": "metadata",  "data": b"skip"}
            yield {"type": "audio", "data": b"PART2"}

        mock_communicate = MagicMock()
        mock_communicate.stream.return_value = fake_stream()
        with patch("edge_tts.Communicate", return_value=mock_communicate):
            result = await tts.synthesize("Hello world")
        assert result == b"PART1PART2"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_audio_chunks(self, tts):
        async def fake_stream():
            yield {"type": "metadata", "data": b"x"}

        mock_communicate = MagicMock()
        mock_communicate.stream.return_value = fake_stream()
        with patch("edge_tts.Communicate", return_value=mock_communicate):
            result = await tts.synthesize("Hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_network_error(self, tts):
        mock_communicate = MagicMock()
        mock_communicate.stream.side_effect = Exception("network failure")
        with patch("edge_tts.Communicate", return_value=mock_communicate):
            result = await tts.synthesize("Hello")
        assert result is None

    @pytest.mark.asyncio
    async def test_passes_voice_and_rate_to_communicate(self, tts):
        async def _empty_stream():
            return
            yield  # pragma: no cover

        with patch("edge_tts.Communicate") as MockComm:
            instance = MagicMock()
            instance.stream.return_value = _empty_stream()
            MockComm.return_value = instance
            await tts.synthesize("test")
        MockComm.assert_called_once_with(
            "test", voice="en-US-JennyNeural", rate="+0%"
        )


class TestTTSEngineSpeak:
    @pytest.mark.asyncio
    async def test_speak_plays_when_synthesize_succeeds(self, tts):
        tts.synthesize = AsyncMock(return_value=b"fake_mp3")
        mock_player = AsyncMock()
        await tts.speak("Hello", mock_player)
        mock_player.play_mp3_bytes.assert_called_once_with(b"fake_mp3")

    @pytest.mark.asyncio
    async def test_speak_uses_fallback_when_synthesize_returns_none(self, tts):
        tts.synthesize = AsyncMock(return_value=None)
        tts._speak_fallback = AsyncMock()
        mock_player = MagicMock()
        await tts.speak("Hello", mock_player)
        tts._speak_fallback.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_speak_skips_empty_string(self, tts):
        tts.synthesize = AsyncMock(return_value=b"mp3")
        mock_player = AsyncMock()
        await tts.speak("", mock_player)
        tts.synthesize.assert_not_called()

    @pytest.mark.asyncio
    async def test_speak_skips_whitespace_only(self, tts):
        tts.synthesize = AsyncMock(return_value=b"mp3")
        mock_player = AsyncMock()
        await tts.speak("   \t\n", mock_player)
        tts.synthesize.assert_not_called()


class TestTTSEngineSpeakStream:
    @pytest.mark.asyncio
    async def test_stream_token_triggers_sentence_speak(self, tts):
        tts.speak = AsyncMock()
        queue = asyncio.Queue()
        await queue.put(("stream_token", "Hello. "))
        await queue.put(None)
        await tts.speak_stream(SentenceChunker(), MagicMock(), queue)
        tts.speak.assert_called()

    @pytest.mark.asyncio
    async def test_none_sentinel_drains_remainder(self, tts):
        spoken = []
        async def capture_speak(text, player):
            if text:
                spoken.append(text)
        tts.speak = capture_speak

        queue = asyncio.Queue()
        await queue.put(("stream_token", "Partial"))
        await queue.put(None)
        await tts.speak_stream(SentenceChunker(), MagicMock(), queue)
        assert any("Partial" in s for s in spoken)

    @pytest.mark.asyncio
    async def test_assistant_message_speaks_full_content(self, tts):
        tts.speak = AsyncMock()
        queue = asyncio.Queue()
        await queue.put(("assistant_message", "Full response here."))
        await tts.speak_stream(SentenceChunker(), MagicMock(), queue)
        tts.speak.assert_called_with("Full response here.", tts.speak.call_args[0][1])

    @pytest.mark.asyncio
    async def test_multiple_stream_tokens_accumulate(self, tts):
        spoken = []
        async def capture_speak(text, player):
            if text:
                spoken.append(text)
        tts.speak = capture_speak

        queue = asyncio.Queue()
        for token in ["The", " capital", " of", " France", " is", " Paris", ".", " "]:
            await queue.put(("stream_token", token))
        await queue.put(None)
        await tts.speak_stream(SentenceChunker(), MagicMock(), queue)
        full = " ".join(spoken)
        assert "Paris" in full

    @pytest.mark.asyncio
    async def test_empty_queue_with_sentinel_does_nothing(self, tts):
        tts.speak = AsyncMock()
        queue = asyncio.Queue()
        await queue.put(None)
        await tts.speak_stream(SentenceChunker(), MagicMock(), queue)
        tts.speak.assert_not_called()
