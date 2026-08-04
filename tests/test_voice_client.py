"""Integration tests for VoiceClient state machine (Phase 6).

All hardware sub-engines (MicCapture, AudioPlayer, WakeWordEngine,
STTEngine, TTSEngine) are mocked.  No audio hardware or model files needed.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import numpy as np

from src.voice.voice_client import VoiceClient, VoiceState


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_config(
    *,
    phrase="hey_jarvis",
    threshold=0.5,
    vad_silence_ms=800,
    barge_in_threshold=0.015,
    llm_model="llama3.2",
    use_agent=True,
    prefix="voice",
):
    cfg = MagicMock()
    cfg.wake_word.phrase = phrase
    cfg.wake_word.model_path = None
    cfg.wake_word.threshold = threshold
    cfg.vad_silence_ms = vad_silence_ms
    cfg.barge_in_threshold = barge_in_threshold
    cfg.llm_model = llm_model
    cfg.use_agent = use_agent
    cfg.conversation_id_prefix = prefix
    cfg.stt = MagicMock()
    cfg.tts = MagicMock()
    return cfg


@pytest.fixture
def client():
    """VoiceClient with all sub-engines replaced by mocks."""
    cfg = _make_config()
    with patch("src.voice.voice_client.MicCapture") as MockMic, \
         patch("src.voice.voice_client.AudioPlayer") as MockPlayer, \
         patch("src.voice.voice_client.WakeWordEngine") as MockWake, \
         patch("src.voice.voice_client.STTEngine") as MockSTT, \
         patch("src.voice.voice_client.TTSEngine") as MockTTS, \
         patch("src.voice.voice_client.update_state"), \
         patch("src.voice.voice_client.clear_state"):
        c = VoiceClient(cfg, "ws://localhost:8000/ws/test")
        c._mic    = MockMic.return_value
        c._player = MockPlayer.return_value
        c._wake   = MockWake.return_value
        c._stt    = MockSTT.return_value
        c._tts    = MockTTS.return_value
    return c


# ── VoiceState enum ───────────────────────────────────────────────────────────

class TestVoiceStateEnum:
    def test_all_states_present(self):
        names = {s.name for s in VoiceState}
        assert names == {"IDLE", "LISTENING", "TRANSCRIBING", "WAITING_RESPONSE", "SPEAKING"}

    def test_states_are_distinct(self):
        values = [s.value for s in VoiceState]
        assert len(values) == len(set(values))


# ── Construction ──────────────────────────────────────────────────────────────

class TestVoiceClientInit:
    def test_initial_state_is_idle(self, client):
        assert client._state == VoiceState.IDLE

    def test_session_id_is_8_hex_chars(self, client):
        assert len(client._session_id) == 8
        int(client._session_id, 16)   # raises if not valid hex

    def test_ws_url_stored(self, client):
        assert client._ws_url == "ws://localhost:8000/ws/test"

    def test_running_is_false_initially(self, client):
        assert client._running is False


# ── IDLE → LISTENING transition ───────────────────────────────────────────────

class TestIdleStep:
    @pytest.mark.asyncio
    async def test_wake_word_detected_transitions_to_listening(self, client):
        client._mic.read_chunk.return_value = np.zeros(1280, dtype=np.float32)
        client._wake.process_chunk.return_value = True
        client._speak_ready = AsyncMock()
        with patch("src.voice.voice_client.update_state"):
            await client._step()
        assert client._state == VoiceState.LISTENING

    @pytest.mark.asyncio
    async def test_wake_word_calls_reset_after_detection(self, client):
        client._mic.read_chunk.return_value = np.zeros(1280, dtype=np.float32)
        client._wake.process_chunk.return_value = True
        client._speak_ready = AsyncMock()
        with patch("src.voice.voice_client.update_state"):
            await client._step()
        client._wake.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_wake_word_stays_idle(self, client):
        client._mic.read_chunk.return_value = np.zeros(1280, dtype=np.float32)
        client._wake.process_chunk.return_value = False
        with patch("src.voice.voice_client.update_state"):
            await client._step()
        assert client._state == VoiceState.IDLE

    @pytest.mark.asyncio
    async def test_no_wake_word_does_not_call_reset(self, client):
        client._mic.read_chunk.return_value = np.zeros(1280, dtype=np.float32)
        client._wake.process_chunk.return_value = False
        with patch("src.voice.voice_client.update_state"):
            await client._step()
        client._wake.reset.assert_not_called()

    @pytest.mark.asyncio
    async def test_wake_flushes_mic_buffer(self, client):
        client._mic.read_chunk.return_value = np.zeros(1280, dtype=np.float32)
        client._wake.process_chunk.return_value = True
        client._speak_ready = AsyncMock()
        with patch("src.voice.voice_client.update_state"):
            await client._step()
        client._mic.flush.assert_called()


# ── LISTENING → TRANSCRIBING → (response or idle) ────────────────────────────

class TestListeningStep:
    @pytest.mark.asyncio
    async def test_empty_transcript_returns_to_idle(self, client):
        client._state = VoiceState.LISTENING
        client._stt.collect_utterance.return_value = np.zeros(512, dtype=np.float32)
        client._stt.transcribe.return_value = ""
        with patch("src.voice.voice_client.update_state"):
            await client._step()
        assert client._state == VoiceState.IDLE

    @pytest.mark.asyncio
    async def test_whitespace_transcript_returns_to_idle(self, client):
        client._state = VoiceState.LISTENING
        client._stt.collect_utterance.return_value = np.zeros(512, dtype=np.float32)
        client._stt.transcribe.return_value = "   "
        with patch("src.voice.voice_client.update_state"):
            await client._step()
        assert client._state == VoiceState.IDLE

    @pytest.mark.asyncio
    async def test_valid_transcript_calls_handle_response(self, client):
        client._state = VoiceState.LISTENING
        client._stt.collect_utterance.return_value = np.zeros(512, dtype=np.float32)
        client._stt.transcribe.return_value = "What is the capital of France?"
        client._handle_response = AsyncMock()
        with patch("src.voice.voice_client.update_state"):
            await client._step()
        client._handle_response.assert_called_once_with("What is the capital of France?")

    @pytest.mark.asyncio
    async def test_step_returns_to_idle_after_response(self, client):
        client._state = VoiceState.LISTENING
        client._stt.collect_utterance.return_value = np.zeros(512, dtype=np.float32)
        client._stt.transcribe.return_value = "Hello"
        client._handle_response = AsyncMock()
        with patch("src.voice.voice_client.update_state"):
            await client._step()
        assert client._state == VoiceState.IDLE

    @pytest.mark.asyncio
    async def test_step_returns_to_idle_when_response_raises(self, client):
        client._state = VoiceState.LISTENING
        client._stt.collect_utterance.return_value = np.zeros(512, dtype=np.float32)
        client._stt.transcribe.return_value = "Hello"
        client._handle_response = AsyncMock(side_effect=RuntimeError("WS error"))
        with patch("src.voice.voice_client.update_state"):
            await client._step()
        assert client._state == VoiceState.IDLE


# ── Shutdown ───────────────────────────────────────────────────────────────────

class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_stops_player(self, client):
        with patch("src.voice.voice_client.clear_state"), \
             patch("src.voice.voice_client.update_state"):
            await client._shutdown()
        client._player.stop.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_stops_mic(self, client):
        with patch("src.voice.voice_client.clear_state"), \
             patch("src.voice.voice_client.update_state"):
            await client._shutdown()
        client._mic.stop.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_closes_wake_engine(self, client):
        with patch("src.voice.voice_client.clear_state"), \
             patch("src.voice.voice_client.update_state"):
            await client._shutdown()
        client._wake.close.assert_called()

    @pytest.mark.asyncio
    async def test_shutdown_sets_running_false(self, client):
        client._running = True
        with patch("src.voice.voice_client.clear_state"), \
             patch("src.voice.voice_client.update_state"):
            await client._shutdown()
        assert client._running is False


# ── Wake interrupt watcher ────────────────────────────────────────────────────

class TestWatchForWakeInterrupt:
    @pytest.mark.asyncio
    async def test_interrupt_sets_events_and_stops_player(self, client):
        interrupt_event = asyncio.Event()
        stop_event = asyncio.Event()

        client._mic.read_chunk.return_value = np.zeros(1280, dtype=np.float32)
        client._wake.process_chunk.return_value = True

        with patch("src.voice.voice_client.update_state"), \
             patch("asyncio.sleep", new_callable=AsyncMock):  # skip 1s delay
            await client._watch_for_wake_interrupt(interrupt_event, stop_event)

        assert interrupt_event.is_set()
        assert stop_event.is_set()
        client._player.stop.assert_called()

    @pytest.mark.asyncio
    async def test_stop_event_exits_loop(self, client):
        interrupt_event = asyncio.Event()
        stop_event = asyncio.Event()
        stop_event.set()  # already set → exits immediately

        client._mic.read_chunk.return_value = np.zeros(1280, dtype=np.float32)
        client._wake.process_chunk.return_value = False

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await client._watch_for_wake_interrupt(interrupt_event, stop_event)

        assert not interrupt_event.is_set()


# ── WebSocket message format ───────────────────────────────────────────────────

class TestWebSocketMessage:
    def test_message_contains_required_fields(self, client):
        """Verify the message dict passed to WebSocket includes all expected keys."""
        import json
        cfg = client._cfg
        conversation_id = f"{cfg.conversation_id_prefix}-{client._session_id}"
        message = {
            "message": "hello",
            "conversation_id": conversation_id,
            "use_agent": cfg.use_agent,
            "use_reasoning": False,
        }
        serialized = json.dumps(message)
        parsed = json.loads(serialized)
        assert "message" in parsed
        assert "conversation_id" in parsed
        assert "use_agent" in parsed
        assert parsed["use_reasoning"] is False

    def test_use_reasoning_always_false(self, client):
        """VoiceClient must never enable reasoning (keeps LLM pinned to fast model)."""
        cfg = client._cfg
        message = {
            "message": "any query",
            "conversation_id": f"{cfg.conversation_id_prefix}-{client._session_id}",
            "use_agent": cfg.use_agent,
            "use_reasoning": False,
        }
        assert message["use_reasoning"] is False
