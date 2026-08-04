import logging
from typing import TYPE_CHECKING, List

import numpy as np

if TYPE_CHECKING:
    from .audio_io import MicCapture
    from ..config.models import VoiceSTTConfig

logger = logging.getLogger("rag_chatbot.voice.stt")


class SileroVAD:
    """Voice Activity Detection using silero-vad PyPI package.

    Processes 512-sample (32 ms) float32 chunks at 16 kHz.
    Falls back to energy-based VAD if silero-vad is unavailable.
    """

    CHUNK_SAMPLES = 512
    SPEECH_THRESHOLD = 0.5
    ENERGY_FALLBACK_THRESHOLD = 0.005

    def __init__(self):
        self._use_silero = False
        self._model = None
        try:
            import torch
            from silero_vad import load_silero_vad
            self._model = load_silero_vad()
            self._torch = torch
            self._use_silero = True
            logger.info("SileroVAD loaded successfully")
        except Exception as e:
            logger.warning(
                f"silero-vad unavailable ({e}), using energy-based VAD fallback"
            )

    def is_speech(self, chunk: np.ndarray) -> bool:
        """Return True if chunk contains speech."""
        if self._use_silero and self._model is not None:
            try:
                tensor = self._torch.from_numpy(chunk.astype(np.float32))
                confidence = self._model(tensor, 16000).item()
                return confidence > self.SPEECH_THRESHOLD
            except Exception as e:
                logger.debug(f"Silero inference error, falling back: {e}")

        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
        return rms > self.ENERGY_FALLBACK_THRESHOLD


class STTEngine:
    """Speech-to-text using faster-whisper with integrated VAD.

    Collects audio from a running MicCapture until a configurable
    silence window elapses, then transcribes with faster-whisper.
    CoreML acceleration is automatic on Apple Silicon via 'cpu' device.
    """

    def __init__(self, config: "VoiceSTTConfig"):
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError(
                "faster-whisper is not installed. Run: pip install faster-whisper"
            )

        from faster_whisper import WhisperModel
        logger.info(
            f"Loading faster-whisper model '{config.model_size}' "
            f"(device={config.device}, compute_type={config.compute_type})"
        )
        self._model = WhisperModel(
            config.model_size,
            device=config.device,
            compute_type=config.compute_type,
        )
        self._language = config.language
        self._vad = SileroVAD()
        logger.info("STTEngine ready")

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe a float32 16 kHz numpy array to text."""
        try:
            segments, _info = self._model.transcribe(
                audio,
                language=self._language,
                beam_size=3,
                vad_filter=True,
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def collect_utterance(
        self, mic: "MicCapture", silence_ms: int
    ) -> np.ndarray:
        """Capture audio until silence_ms of consecutive silence after speech onset.

        Discards pre-speech silence; includes trailing silence for natural sentence
        boundaries. Returns a float32 16 kHz mono numpy array.
        """
        chunk_samples = SileroVAD.CHUNK_SAMPLES
        ms_per_chunk = int(chunk_samples / 16000 * 1000)
        silence_chunks_needed = max(1, silence_ms // ms_per_chunk)

        speech_frames: List[np.ndarray] = []
        consecutive_silence = 0
        started = False

        while True:
            chunk = mic.read_chunk(chunk_samples)
            is_speech = self._vad.is_speech(chunk)

            if is_speech:
                started = True
                consecutive_silence = 0
                speech_frames.append(chunk)
            elif started:
                consecutive_silence += 1
                speech_frames.append(chunk)
                if consecutive_silence >= silence_chunks_needed:
                    break

        return np.concatenate(speech_frames, axis=0) if speech_frames else np.zeros(chunk_samples, dtype=np.float32)
