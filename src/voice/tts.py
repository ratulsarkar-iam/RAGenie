import asyncio
import logging
import re
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from .audio_io import AudioPlayer
    from ..config.models import VoiceTTSConfig

logger = logging.getLogger("rag_chatbot.voice.tts")


class SentenceChunker:
    """Accumulates streaming LLM tokens and emits complete sentences for TTS.

    A sentence boundary fires on: '. ', '? ', '! ', '.\n', '!\n', '?\n',
    or when the buffer exceeds MAX_BUFFER_CHARS (forces a flush for very
    long run-on sentences).
    """

    _BOUNDARY = re.compile(r"(?<=[.!?])\s+|(?<=[.!?])$")
    MAX_BUFFER_CHARS = 120

    def __init__(self):
        self._buffer: str = ""

    def feed(self, token: str) -> List[str]:
        """Append token; return list of complete sentences ready for TTS (may be empty)."""
        self._buffer += token
        parts = self._BOUNDARY.split(self._buffer)

        if len(parts) > 1:
            complete = parts[:-1]
            self._buffer = parts[-1]
            return [s.strip() for s in complete if s.strip()]

        if len(self._buffer) >= self.MAX_BUFFER_CHARS:
            chunk = self._buffer.strip()
            self._buffer = ""
            return [chunk] if chunk else []

        return []

    def drain(self) -> str:
        """Return and clear any remaining buffered text (called on stream_end)."""
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining


class TTSEngine:
    """Text-to-speech using edge-tts (primary) with pyttsx3 as offline fallback.

    edge-tts is free, requires no API key, and uses Microsoft Edge neural
    voices. It makes HTTPS calls to Microsoft — no local model is loaded.
    pyttsx3 uses macOS built-in voices and works fully offline.
    """

    def __init__(self, config: "VoiceTTSConfig"):
        self._engine = config.engine
        self._voice = config.voice
        self._rate = config.rate
        self._fallback = config.fallback_engine

    async def synthesize(self, text: str) -> Optional[bytes]:
        """Synthesize text to MP3 bytes via edge-tts. Returns None on failure."""
        try:
            import edge_tts
        except ImportError:
            logger.warning("edge-tts not installed; using fallback only")
            return None

        try:
            communicate = edge_tts.Communicate(text, voice=self._voice, rate=self._rate)
            chunks: List[bytes] = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            return b"".join(chunks) if chunks else None
        except Exception as e:
            logger.warning(f"edge-tts synthesis failed: {e}")
            return None

    async def _speak_fallback(self, text: str) -> None:
        """Speak text using pyttsx3 (macOS built-in voices, fully offline)."""
        loop = asyncio.get_running_loop()

        def _sync_speak():
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception as e:
                logger.error(f"pyttsx3 fallback error: {e}")

        await loop.run_in_executor(None, _sync_speak)

    async def speak(self, text: str, player: "AudioPlayer") -> None:
        """Synthesize and play a single text fragment."""
        if not text.strip():
            return

        mp3_bytes = await self.synthesize(text)
        if mp3_bytes:
            await player.play_mp3_bytes(mp3_bytes)
        else:
            logger.info("edge-tts unavailable, using pyttsx3 fallback")
            await self._speak_fallback(text)

    async def speak_stream(
        self,
        chunker: SentenceChunker,
        player: "AudioPlayer",
        token_queue: asyncio.Queue,
    ) -> None:
        """Consume a token_queue and speak sentence-by-sentence as tokens arrive.

        Protocol:
        - Items are (event_type, content) tuples or None (sentinel = done).
        - "stream_token"    → feed to chunker, speak completed sentences immediately.
        - "assistant_message" → speak full content at once (non-streaming agent mode).
        - None              → drain chunker remainder and exit.
        """
        while True:
            item: Optional[Tuple[str, str]] = await token_queue.get()

            if item is None:
                remaining = chunker.drain()
                if remaining:
                    await self.speak(remaining, player)
                break

            event_type, content = item

            if event_type == "stream_token":
                sentences = chunker.feed(content)
                for sentence in sentences:
                    await self.speak(sentence, player)

            elif event_type == "assistant_message":
                await self.speak(content, player)
                break
