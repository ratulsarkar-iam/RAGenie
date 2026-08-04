# Spec: tts

## Purpose

Convert LLM text output to spoken audio. Two subcomponents:
1. **`SentenceChunker`** — splits streaming token output into speakable sentence fragments.
2. **`TTSEngine`** — synthesises speech from text using `edge-tts` (primary) or `pyttsx3` (offline fallback), and plays audio via `AudioPlayer`.

## Module

- `src/voice/tts.py`

---

## Why Not Ollama for TTS

Ollama runs large language models (text-in → text-out). It has no audio encoder/decoder. TTS requires dedicated neural vocoder models (e.g. FastSpeech2, VITS, VALL-E) that operate on mel spectrograms and waveforms. These are fundamentally different model architectures that Ollama does not support.

**Selected: `edge-tts`** — Microsoft Edge's neural TTS service accessed via a free public API. No API key, no account, no cost. Quality is equivalent to Azure Neural TTS (which costs ~$16/1M characters). On M3 MacBook Air: zero local RAM, ~50ms synthesis latency per sentence over typical broadband.

---

## `SentenceChunker`

```python
class SentenceChunker:
    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+|(?<=[.!?])$|\n')
    MAX_BUFFER_CHARS = 120
    
    def __init__(self):
        self._buffer: str = ""
    
    def feed(self, token: str) -> List[str]:
        """
        Append token to buffer. Return list of complete sentences ready for TTS.
        Returns empty list if no sentence boundary detected yet.
        """
        self._buffer += token
        sentences = self.SENTENCE_ENDINGS.split(self._buffer)
        
        if len(sentences) > 1:
            complete = sentences[:-1]
            self._buffer = sentences[-1]
            return [s.strip() for s in complete if s.strip()]
        
        # Force flush if buffer exceeds MAX_BUFFER_CHARS (very long sentence)
        if len(self._buffer) >= self.MAX_BUFFER_CHARS:
            chunk = self._buffer
            self._buffer = ""
            return [chunk.strip()]
        
        return []
    
    def drain(self) -> str:
        """Return and clear remaining buffer (called on stream_end)."""
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining
```

### Sentence Boundary Logic

| Input tokens | Fires TTS for |
|---|---|
| `"The capital is Paris."` + `" It has"` | `"The capital is Paris."` |
| `"Are you sure?"` + `" Yes!"` | `"Are you sure?"`, then `"Yes!"` |
| 120+ chars with no punctuation | entire buffer forced out |
| `stream_end` event | `drain()` → remaining buffer |

---

## `TTSEngine`

```python
class TTSEngine:
    def __init__(self, config: VoiceTTSConfig)
    async def synthesize(self, text: str) -> bytes
    async def speak(self, text: str, player: "AudioPlayer") -> None
    async def speak_stream(
        self,
        chunker: SentenceChunker,
        player: "AudioPlayer",
        token_queue: asyncio.Queue,
    ) -> None
```

### `__init__`

```python
def __init__(self, config: VoiceTTSConfig):
    self._engine = config.engine
    self._voice = config.voice
    self._rate = config.rate
    self._fallback = config.fallback_engine
```

### `async synthesize(text: str) -> bytes`

```python
async def synthesize(self, text: str) -> bytes:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=self._voice, rate=self._rate)
    audio_chunks: List[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])
    return b"".join(audio_chunks)
```

- Returns raw MP3 bytes.
- `edge_tts.Communicate.stream()` yields audio chunks as they arrive — the first chunk typically arrives within 150–300 ms.
- On `aiohttp.ClientError` or `asyncio.TimeoutError`, falls back to `_synthesize_fallback(text)`.

### `async _synthesize_fallback(text: str) -> None`

```python
async def _synthesize_fallback(self, text: str) -> None:
    """Use pyttsx3 (macOS built-in voices) when edge-tts is unreachable."""
    import pyttsx3
    loop = asyncio.get_event_loop()
    def _speak_sync():
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
    await loop.run_in_executor(None, _speak_sync)
```

### `async speak(text: str, player: AudioPlayer) -> None`

```python
async def speak(self, text: str, player: AudioPlayer) -> None:
    try:
        mp3_bytes = await asyncio.wait_for(self.synthesize(text), timeout=5.0)
        await player.play_mp3_bytes(mp3_bytes)
    except (Exception,) as e:
        logger.warning(f"edge-tts failed ({e}), using fallback")
        await self._synthesize_fallback(text)
```

### `async speak_stream(chunker, player, token_queue) -> None`

This is the main coroutine for streaming TTS during LLM generation. It consumes tokens from `token_queue` (populated by the WebSocket handler), feeds them to `SentenceChunker`, and calls `speak()` per sentence:

```python
async def speak_stream(
    self,
    chunker: SentenceChunker,
    player: AudioPlayer,
    token_queue: asyncio.Queue,
) -> None:
    while True:
        item = await token_queue.get()
        
        if item is None:  # sentinel: stream_end
            remaining = chunker.drain()
            if remaining:
                await self.speak(remaining, player)
            break
        
        token_type, content = item
        if token_type == "stream_token":
            sentences = chunker.feed(content)
            for sentence in sentences:
                await self.speak(sentence, player)
        elif token_type == "assistant_message":
            # non-streaming agent response — speak full text
            await self.speak(content, player)
            break
```

---

## `AudioPlayer` (in `src/voice/audio_io.py`)

```python
class AudioPlayer:
    def __init__(self)
    async def play_mp3_bytes(self, mp3_bytes: bytes) -> None
    def stop(self) -> None
    def is_playing(self) -> bool
```

**`play_mp3_bytes`:**

```python
async def play_mp3_bytes(self, mp3_bytes: bytes) -> None:
    import io, soundfile as sf, sounddevice as sd
    audio_data, sample_rate = sf.read(io.BytesIO(mp3_bytes), dtype="float32")
    self._stop_flag = False
    self._playing = True
    
    CHUNK = 1024
    idx = 0
    with sd.OutputStream(samplerate=sample_rate, channels=audio_data.shape[-1] if audio_data.ndim > 1 else 1, dtype="float32") as stream:
        while idx < len(audio_data) and not self._stop_flag:
            end = min(idx + CHUNK, len(audio_data))
            stream.write(audio_data[idx:end])
            idx = end
            await asyncio.sleep(0)  # yield to event loop for barge-in check
    
    self._playing = False
```

- `soundfile.read` decodes MP3 bytes via libsndfile.
- Chunked write with `await asyncio.sleep(0)` ensures the barge-in check in `VoiceClient` can set `_stop_flag` between chunks.

**`stop()`:** Sets `self._stop_flag = True` — checked in the playback loop above.

---

## edge-tts Voice Options

Recommended voices for RAGenie (run `python -m edge_tts --list-voices | grep en-`):

| Voice | Accent | Character |
|---|---|---|
| `en-US-JennyNeural` | American | Warm, assistant-like (default) |
| `en-US-GuyNeural` | American | Friendly male |
| `en-GB-SoniaNeural` | British | Professional |
| `en-IN-NeerjaNeural` | Indian | Natural Indian English |
| `en-IN-PrabhatNeural` | Indian | Male Indian English |

Set via `config.yaml` `voice.tts.voice` — no code change required.

---

## Tests (`tests/test_voice_tts.py`)

```python
def test_sentence_chunker_splits_on_period():
    c = SentenceChunker()
    assert c.feed("Hello world") == []
    assert c.feed(". How ") == ["Hello world."]

def test_sentence_chunker_splits_on_question():
    c = SentenceChunker()
    c.feed("Are you sure")
    result = c.feed("? Yes!")
    assert "Are you sure?" in result

def test_sentence_chunker_force_flush_at_max():
    c = SentenceChunker()
    long_token = "a" * 120
    result = c.feed(long_token)
    assert result == [long_token]

def test_sentence_chunker_drain_returns_remaining():
    c = SentenceChunker()
    c.feed("incomplete sentence")
    assert c.drain() == "incomplete sentence"
    assert c.drain() == ""  # second drain returns empty

async def test_tts_engine_synthesize(mock_edge_tts_communicate):
    mock_edge_tts_communicate.return_value.stream.return_value = aiter([
        {"type": "audio", "data": b"mp3data"},
        {"type": "WordBoundary", "data": {}},
    ])
    engine = TTSEngine(VoiceTTSConfig())
    result = await engine.synthesize("Hello")
    assert result == b"mp3data"

async def test_tts_engine_fallback_on_network_error(mock_edge_tts_communicate, mock_pyttsx3):
    mock_edge_tts_communicate.side_effect = aiohttp.ClientError("no network")
    engine = TTSEngine(VoiceTTSConfig())
    player = MagicMock(spec=AudioPlayer)
    await engine.speak("Hello", player)
    mock_pyttsx3.init.assert_called_once()

async def test_speak_stream_processes_tokens():
    engine = TTSEngine(VoiceTTSConfig())
    chunker = SentenceChunker()
    player = AsyncMock(spec=AudioPlayer)
    queue = asyncio.Queue()
    await queue.put(("stream_token", "Hello world."))
    await queue.put(None)  # sentinel
    with patch.object(engine, "speak", new_callable=AsyncMock) as mock_speak:
        await engine.speak_stream(chunker, player, queue)
        mock_speak.assert_called_once_with("Hello world.", player)
```
