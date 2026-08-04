"""Unit tests for voice assistant configuration models (Phase 1)."""
import pytest
from pydantic import ValidationError

from src.config.models import (
    Config,
    VoiceConfig,
    VoiceSTTConfig,
    VoiceTTSConfig,
    VoiceWakeWordConfig,
)


class TestVoiceWakeWordConfig:
    def test_defaults(self):
        cfg = VoiceWakeWordConfig()
        assert cfg.phrase == "hey_jarvis"
        assert cfg.model_path is None
        assert cfg.threshold == 0.5

    def test_custom_phrase_and_threshold(self):
        cfg = VoiceWakeWordConfig(phrase="hey_ragenie", threshold=0.3)
        assert cfg.phrase == "hey_ragenie"
        assert cfg.threshold == 0.3

    def test_threshold_upper_bound(self):
        with pytest.raises(ValidationError):
            VoiceWakeWordConfig(threshold=1.5)

    def test_threshold_lower_bound(self):
        with pytest.raises(ValidationError):
            VoiceWakeWordConfig(threshold=-0.1)

    def test_custom_model_path(self):
        cfg = VoiceWakeWordConfig(model_path="/data/voice/hey_ragenie.onnx")
        assert cfg.model_path == "/data/voice/hey_ragenie.onnx"


class TestVoiceSTTConfig:
    def test_defaults(self):
        cfg = VoiceSTTConfig()
        assert cfg.engine == "faster-whisper"
        assert cfg.model_size == "base"
        assert cfg.language == "en"
        assert cfg.device == "cpu"
        assert cfg.compute_type == "int8"

    def test_custom_model_size(self):
        cfg = VoiceSTTConfig(model_size="small")
        assert cfg.model_size == "small"


class TestVoiceTTSConfig:
    def test_defaults(self):
        cfg = VoiceTTSConfig()
        assert cfg.engine == "edge-tts"
        assert cfg.voice == "en-US-JennyNeural"
        assert cfg.rate == "+0%"
        assert cfg.fallback_engine == "pyttsx3"

    def test_custom_voice(self):
        cfg = VoiceTTSConfig(voice="en-GB-RyanNeural")
        assert cfg.voice == "en-GB-RyanNeural"


class TestVoiceConfig:
    def test_defaults(self):
        cfg = VoiceConfig()
        assert cfg.enabled is False
        assert isinstance(cfg.wake_word, VoiceWakeWordConfig)
        assert isinstance(cfg.stt, VoiceSTTConfig)
        assert isinstance(cfg.tts, VoiceTTSConfig)
        assert cfg.vad_silence_ms == 800
        assert cfg.barge_in_threshold == 0.015
        assert cfg.llm_model == "llama3.2"
        assert cfg.use_agent is True
        assert cfg.conversation_id_prefix == "voice"

    def test_enabled_true(self):
        cfg = VoiceConfig(enabled=True)
        assert cfg.enabled is True

    def test_nested_wake_word_dict(self):
        cfg = VoiceConfig(wake_word={"phrase": "hey_ragenie", "threshold": 0.4})
        assert cfg.wake_word.phrase == "hey_ragenie"
        assert cfg.wake_word.threshold == 0.4

    def test_nested_stt_dict(self):
        cfg = VoiceConfig(stt={"model_size": "small", "language": "fr"})
        assert cfg.stt.model_size == "small"
        assert cfg.stt.language == "fr"

    def test_nested_tts_dict(self):
        cfg = VoiceConfig(tts={"voice": "en-GB-RyanNeural"})
        assert cfg.tts.voice == "en-GB-RyanNeural"

    def test_conversation_id_prefix_custom(self):
        cfg = VoiceConfig(conversation_id_prefix="jarvis")
        assert cfg.conversation_id_prefix == "jarvis"


class TestConfigRoot:
    def test_voice_field_present_on_root(self):
        cfg = Config()
        assert hasattr(cfg, "voice")
        assert isinstance(cfg.voice, VoiceConfig)

    def test_voice_defaults_on_root(self):
        cfg = Config()
        assert cfg.voice.wake_word.phrase == "hey_jarvis"
        assert cfg.voice.stt.model_size == "base"
        assert cfg.voice.tts.voice == "en-US-JennyNeural"

    def test_load_config_from_yaml(self):
        from src.config.loader import load_config
        cfg = load_config()
        assert isinstance(cfg.voice, VoiceConfig)
        assert cfg.voice.wake_word.phrase == "hey_jarvis"
        assert cfg.voice.enabled is True   # set to true in config.yaml
