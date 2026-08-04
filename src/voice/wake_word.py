import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger("rag_chatbot.voice.wake_word")


def _play_activation_beep() -> None:
    """Play a short 880 Hz sine-wave beep to confirm wake word detection."""
    try:
        import sounddevice as sd
        t = np.linspace(0, 0.15, int(16000 * 0.15), dtype=np.float32)
        beep = (0.3 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
        sd.play(beep, samplerate=16000, blocking=True)
    except Exception as e:
        logger.debug(f"Beep skipped: {e}")


class WakeWordEngine:
    """Detects the configured wake phrase using openWakeWord.

    Feeds 80 ms (1280-sample) float32 audio chunks at 16 kHz.
    Returns True from process_chunk() exactly once per wake event;
    subsequent calls are suppressed for ~3.8 s (cooldown) to prevent
    the spoken response from re-triggering detection.
    """

    CHUNK_SAMPLES = 1280
    COOLDOWN_CHUNKS = 48

    def __init__(
        self,
        phrase: str = "hey_jarvis",
        model_path: Optional[str] = None,
        threshold: float = 0.5,
    ):
        try:
            from openwakeword.model import Model as OWWModel
        except ImportError:
            raise RuntimeError(
                "openwakeword is not installed. Run: pip install openwakeword"
            )

        if model_path and os.path.exists(model_path):
            self._model = OWWModel(wakeword_models=[model_path], inference_framework="onnx")
            self._model_key = os.path.splitext(os.path.basename(model_path))[0]
            logger.info(f"WakeWordEngine loaded custom model: {model_path}")
        else:
            self._model = OWWModel(wakeword_models=[phrase], inference_framework="onnx")
            self._model_key = phrase
            logger.info(f"WakeWordEngine loaded bundled model for phrase: '{phrase}'")

        self._threshold = threshold
        self._cooldown_frames = 0

    def process_chunk(self, audio: np.ndarray,
                       threshold: Optional[float] = None) -> bool:
        """Feed one 1280-sample float32 chunk. Returns True if wake word detected.

        *threshold* overrides the instance threshold for this single call —
        useful for interrupt detection where a lower value (e.g. 0.30) is
        preferred because TTS audio leaking into the mic raises the noise floor.
        """
        if self._cooldown_frames > 0:
            self._cooldown_frames -= 1
            return False

        effective_threshold = threshold if threshold is not None else self._threshold

        try:
            audio_int16 = (audio * 32768).clip(-32768, 32767).astype(np.int16)
            prediction = self._model.predict(audio_int16)
            score = prediction.get(self._model_key, 0.0)
            if score > 0.05:
                logger.debug(f"Wake word score={score:.3f} (threshold={effective_threshold})")
            if score >= effective_threshold:
                logger.info(f"Wake word detected! score={score:.3f} (threshold={effective_threshold})")
                self._cooldown_frames = self.COOLDOWN_CHUNKS
                _play_activation_beep()
                return True
        except Exception as e:
            logger.warning(f"WakeWordEngine prediction error: {e}")

        return False

    def reset(self) -> None:
        """Clear accumulated state and cooldown after a session completes."""
        try:
            self._model.reset()
        except Exception:
            pass
        self._cooldown_frames = 0

    def close(self) -> None:
        self.reset()
