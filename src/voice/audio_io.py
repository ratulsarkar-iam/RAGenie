import asyncio
import logging
import os
import tempfile
import time
from collections import deque
from typing import Optional

import numpy as np

logger = logging.getLogger("rag_chatbot.voice.audio_io")


class MicCapture:
    """Continuous microphone capture using sounddevice with a deque ring buffer.

    Runs a sounddevice InputStream callback on a background thread; all
    audio is stored in self._buffer as mono float32 chunks at 16 kHz.
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    DTYPE = "float32"
    BLOCK_SIZE = 512

    def __init__(self, device: Optional[int] = None):
        self._device = device
        self._buffer: deque = deque()
        self._stream = None

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            raise RuntimeError("sounddevice is not installed. Run: pip install sounddevice")

        import sounddevice as sd
        self._stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
            dtype=self.DTYPE,
            blocksize=self.BLOCK_SIZE,
            device=self._device,
            callback=self._callback,
        )
        self._stream.start()
        logger.info("MicCapture started")

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            logger.debug(f"MicCapture status: {status}")
        self._buffer.append(indata[:, 0].copy())

    def read_chunk(self, n_frames: int) -> np.ndarray:
        """Block (with small sleeps) until n_frames are available, return float32 array."""
        accumulated = []
        total = 0
        while total < n_frames:
            if self._buffer:
                chunk = self._buffer.popleft()
                accumulated.append(chunk)
                total += len(chunk)
            else:
                time.sleep(0.005)
        audio = np.concatenate(accumulated)
        return audio[:n_frames]

    def get_rms(self, window_ms: int = 200) -> float:
        """Return RMS energy of the last window_ms of buffered audio."""
        n = int(self.SAMPLE_RATE * window_ms / 1000)
        if not self._buffer:
            return 0.0
        recent_chunks = list(self._buffer)
        recent = np.concatenate(recent_chunks) if recent_chunks else np.zeros(1, dtype=np.float32)
        tail = recent[-n:] if len(recent) >= n else recent
        return float(np.sqrt(np.mean(tail ** 2)))

    def flush(self) -> None:
        """Discard all buffered audio (call after TTS playback to avoid echo)."""
        self._buffer.clear()

    def stop(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            logger.info("MicCapture stopped")


class AudioPlayer:
    """Async audio player using macOS afplay (zero extra dependencies).

    Uses a temp MP3 file + afplay subprocess so barge-in can terminate
    playback immediately via stop().
    """

    def __init__(self):
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._playing: bool = False
        self._tmp_path: Optional[str] = None

    async def play_mp3_bytes(self, mp3_bytes: bytes) -> None:
        """Decode MP3 bytes and play audio.

        Primary path  (macOS) : afplay via subprocess — zero extra deps,
                                 barge-in via process termination.
        Fallback path (cross-platform) : decode with miniaudio → PCM →
                                 sounddevice.play(), used when afplay is absent.
        """
        self._playing = True
        try:
            await self._play_afplay(mp3_bytes)
        except FileNotFoundError:
            logger.info("afplay not found — falling back to sounddevice")
            await self._play_sounddevice(mp3_bytes)
        except Exception as e:
            logger.error(f"AudioPlayer error: {e}")
        finally:
            self._playing = False
            self._proc = None
            self._cleanup_tmp()

    async def _play_afplay(self, mp3_bytes: bytes) -> None:
        """macOS-native playback via afplay subprocess."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(mp3_bytes)
            self._tmp_path = f.name
        self._proc = await asyncio.create_subprocess_exec(
            "afplay", self._tmp_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await self._proc.wait()

    async def _play_sounddevice(self, mp3_bytes: bytes) -> None:
        """Cross-platform playback: decode MP3 → PCM via miniaudio, play via sounddevice."""
        loop = asyncio.get_running_loop()

        def _sync_play():
            try:
                import miniaudio
                import sounddevice as sd
                decoded = miniaudio.decode(mp3_bytes, nchannels=1, output_format=miniaudio.SampleFormat.FLOAT32)
                pcm = np.frombuffer(decoded.samples, dtype=np.float32)
                sd.play(pcm, samplerate=decoded.sample_rate, blocking=True)
            except ImportError as e:
                logger.error(f"sounddevice/miniaudio not installed: {e}. "
                             "Run: pip install sounddevice miniaudio")
            except Exception as e:
                logger.error(f"sounddevice playback error: {e}")

        await loop.run_in_executor(None, _sync_play)

    def stop(self) -> None:
        """Interrupt playback immediately (for barge-in / shutdown)."""
        if self._proc and self._proc.returncode is None:
            try:
                self._proc.terminate()   # SIGTERM first (clean)
            except ProcessLookupError:
                pass
            except Exception:
                try:
                    self._proc.kill()    # SIGKILL fallback if SIGTERM fails
                except Exception:
                    pass
        self._playing = False

    def is_playing(self) -> bool:
        return self._playing

    def _cleanup_tmp(self) -> None:
        if self._tmp_path and os.path.exists(self._tmp_path):
            try:
                os.unlink(self._tmp_path)
            except Exception:
                pass
            self._tmp_path = None
