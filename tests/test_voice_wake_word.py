"""Unit tests for WakeWordEngine (Phase 3).

All openwakeword and sounddevice calls are mocked so tests run without
any model downloads or audio hardware.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch, call

SILENCE = np.zeros(1280, dtype=np.float32)
LOUD   = np.ones(1280,  dtype=np.float32)


def _make_engine(phrase="hey_jarvis", threshold=0.5, score=0.0):
    """Return a WakeWordEngine with mocked OWW model returning *score*."""
    mock_model = MagicMock()
    mock_model.predict.return_value = {phrase: score}
    mock_model.reset = MagicMock()

    with patch("openwakeword.model.Model", return_value=mock_model), \
         patch("src.voice.wake_word._play_activation_beep"):
        from src.voice.wake_word import WakeWordEngine
        engine = WakeWordEngine(phrase=phrase, threshold=threshold)
    return engine, mock_model


class TestWakeWordEngineInit:
    def test_loads_bundled_model(self):
        mock_model = MagicMock()
        with patch("openwakeword.model.Model", return_value=mock_model) as MockOWW:
            from src.voice.wake_word import WakeWordEngine
            e = WakeWordEngine(phrase="hey_jarvis", threshold=0.5)
        MockOWW.assert_called_once_with(
            wakeword_models=["hey_jarvis"], inference_framework="onnx"
        )
        assert e._threshold == 0.5
        assert e._model_key == "hey_jarvis"

    def test_loads_custom_model_when_path_exists(self, tmp_path):
        model_file = tmp_path / "custom.onnx"
        model_file.write_bytes(b"fake")
        mock_model = MagicMock()
        with patch("openwakeword.model.Model", return_value=mock_model):
            from src.voice.wake_word import WakeWordEngine
            e = WakeWordEngine(phrase="hey_jarvis", model_path=str(model_file))
        assert e._model_key == "custom"

    def test_raises_without_openwakeword(self):
        with patch.dict("sys.modules", {"openwakeword": None, "openwakeword.model": None}):
            import importlib, sys
            # Force re-import to trigger the ImportError path
            if "src.voice.wake_word" in sys.modules:
                del sys.modules["src.voice.wake_word"]
            with pytest.raises(Exception):
                from src.voice.wake_word import WakeWordEngine
                WakeWordEngine()


class TestProcessChunk:
    def test_no_detection_below_threshold(self):
        engine, _ = _make_engine(score=0.49)
        assert engine.process_chunk(SILENCE) is False

    def test_detection_exactly_at_threshold(self):
        engine, _ = _make_engine(score=0.5)
        with patch("src.voice.wake_word._play_activation_beep"):
            assert engine.process_chunk(SILENCE) is True

    def test_detection_above_threshold(self):
        engine, _ = _make_engine(score=0.95)
        with patch("src.voice.wake_word._play_activation_beep"):
            assert engine.process_chunk(SILENCE) is True

    def test_audio_converted_to_int16_before_predict(self):
        engine, mock_model = _make_engine(score=0.0)
        chunk = np.array([0.5, -0.5, 0.25], dtype=np.float32)
        engine.process_chunk(chunk)
        called_audio = mock_model.predict.call_args[0][0]
        assert called_audio.dtype == np.int16
        assert called_audio[0] == pytest.approx(16384, abs=1)   # 0.5 * 32768

    def test_cooldown_suppresses_immediate_re_detection(self):
        engine, _ = _make_engine(score=0.9)
        with patch("src.voice.wake_word._play_activation_beep"):
            first = engine.process_chunk(SILENCE)
        assert first is True
        # Cooldown active — next chunks suppressed regardless of score
        assert engine.process_chunk(SILENCE) is False
        assert engine.process_chunk(SILENCE) is False

    def test_cooldown_decrements_each_chunk(self):
        engine, _ = _make_engine(score=0.0)
        engine._cooldown_frames = 3
        engine.process_chunk(SILENCE)
        assert engine._cooldown_frames == 2
        engine.process_chunk(SILENCE)
        assert engine._cooldown_frames == 1

    def test_cooldown_expires_after_n_chunks(self):
        engine, _ = _make_engine(score=0.9)
        engine._cooldown_frames = 2
        engine.process_chunk(SILENCE)   # 2→1
        engine.process_chunk(SILENCE)   # 1→0, now expired
        with patch("src.voice.wake_word._play_activation_beep"):
            assert engine.process_chunk(SILENCE) is True

    def test_threshold_override_lower(self):
        """Override threshold 0.3 should fire when default 0.5 would not."""
        engine, _ = _make_engine(score=0.35, threshold=0.5)
        # Default: no detection
        assert engine.process_chunk(SILENCE) is False
        # Override to 0.3: should detect
        with patch("src.voice.wake_word._play_activation_beep"):
            assert engine.process_chunk(SILENCE, threshold=0.3) is True

    def test_threshold_override_higher(self):
        """Override threshold 0.9 should block when default 0.5 would fire."""
        engine, _ = _make_engine(score=0.6, threshold=0.5)
        assert engine.process_chunk(SILENCE, threshold=0.9) is False

    def test_prediction_exception_returns_false(self):
        engine, mock_model = _make_engine(score=0.0)
        mock_model.predict.side_effect = RuntimeError("model crash")
        assert engine.process_chunk(SILENCE) is False

    def test_cooldown_set_to_COOLDOWN_CHUNKS_after_detection(self):
        from src.voice.wake_word import WakeWordEngine
        engine, _ = _make_engine(score=0.9)
        with patch("src.voice.wake_word._play_activation_beep"):
            engine.process_chunk(SILENCE)
        assert engine._cooldown_frames == WakeWordEngine.COOLDOWN_CHUNKS


class TestReset:
    def test_reset_clears_cooldown(self):
        engine, _ = _make_engine()
        engine._cooldown_frames = 42
        engine.reset()
        assert engine._cooldown_frames == 0

    def test_reset_calls_model_reset(self):
        engine, mock_model = _make_engine()
        engine.reset()
        mock_model.reset.assert_called_once()

    def test_close_delegates_to_reset(self):
        engine, _ = _make_engine()
        engine._cooldown_frames = 10
        engine.close()
        assert engine._cooldown_frames == 0
