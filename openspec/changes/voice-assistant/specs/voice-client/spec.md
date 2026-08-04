# Spec: voice-client

## Purpose

Top-level orchestrator (`VoiceClient`) that drives the end-to-end voice pipeline state machine, plus the standalone CLI entry point `voice.py`.

## Modules

- `src/voice/audio_io.py` — `MicCapture` + `AudioPlayer`
- `src/voice/voice_client.py` — `VoiceState` enum + `VoiceClient`
- `voice.py` (project root — CLI entry point)

---

## `MicCapture` (`src/voice/audio_io.py`)

```python
class MicCapture:
    SAMPLE_RATE = 16000
    CHANNELS = 1
    DTYPE = "float32"

    def __init__(self, device: Optional[int] = None)
    def start(self) -> None          # opens sounddevice InputStream, registers callback
    def stop(self) -> None           # closes stream
    def read_chunk(self, n_frames: int) -> np.ndarray   # blocks until n_frames available
    def get_rms(self, window_ms: int = 200) -> float    # RMS of last window_ms audio
```

**Key details:**
- `sounddevice.InputStream` runs its callback on a background thread; audio is pushed into an internal `deque`.
- `read_chunk` blocks in a tight `time.sleep(0.005)` loop until enough frames accumulate, then returns a contiguous float32 array.
- `get_rms` used for barge-in detection — checks RMS of the most recent `window_ms` of audio.

## `AudioPlayer` (`src/voice/audio_io.py`)

```python
class AudioPlayer:
    def __init__(self)
    async def play_mp3_bytes(self, mp3_bytes: bytes) -> None
    def stop(self) -> None        # sets _stop_flag; checked in playback loop
    def is_playing(self) -> bool
```

**Key details:**
- Decodes MP3 bytes via `soundfile.read(io.BytesIO(mp3_bytes))`.
- Writes to `sounddevice.OutputStream` in 1024-sample chunks with `await asyncio.sleep(0)` between each — yields to event loop so barge-in can call `stop()`.
- `stop()` sets `_stop_flag = True`; the playback loop exits on next iteration.

---

## `VoiceState` Enum

```python
from enum import Enum, auto

class VoiceState(Enum):
    IDLE = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    WAITING_RESPONSE = auto()
    SPEAKING = auto()
```

---

## `VoiceClient` (`src/voice/voice_client.py`)

```python
class VoiceClient:
    def __init__(self, config: VoiceConfig, ws_url: str)
    async def run(self) -> None
    async def _handle_response(self, text: str) -> None
    def _check_barge_in(self) -> bool
    async def _shutdown(self) -> None
```

### `__init__`

Instantiates all sub-engines from config:

```python
def __init__(self, config: VoiceConfig, ws_url: str):
    self._cfg = config
    self._ws_url = ws_url
    self._state = VoiceState.IDLE
    self._session_id = str(uuid.uuid4())[:8]

    self._mic    = MicCapture()
    self._player = AudioPlayer()
    self._wake   = WakeWordEngine(
        model_path=config.wake_word.model_path,
        phrase=config.wake_word.phrase,
        threshold=config.wake_word.threshold,
    )
    self._stt = STTEngine(config.stt)
    self._tts = TTSEngine(config.tts)
```

### `async run()`

```python
async def run(self) -> None:
    self._mic.start()
    print(f"\n🎙  Listening for '{self._cfg.wake_word.phrase}'...\n")
    try:
        while True:
            await self._step()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await self._shutdown()
```

### `async _step()`

State machine tick — called in the main loop:

```
IDLE
  └─ read 1280-sample chunk from mic
  └─ if wake_engine.process_chunk(chunk): → LISTENING, beep

LISTENING
  └─ stt.collect_utterance() — blocks until VAD silence
  └─ → TRANSCRIBING
  └─ stt.transcribe(audio) → text
  └─ if no text: back to IDLE
  └─ → WAITING_RESPONSE
  └─ await _handle_response(text)
  └─ → IDLE
```

### `async _handle_response(text)`

Opens a WebSocket to `ws_url`, sends the user message, routes `stream_token` / `assistant_message` events to `TTSEngine.speak_stream()` concurrently:

```python
message = {
    "message": text,
    "conversation_id": f"{self._cfg.conversation_id_prefix}-{self._session_id}",
    "use_agent": self._cfg.use_agent,
    "use_reasoning": False,   # never use reasoning model in voice mode
}
```

- A `token_queue: asyncio.Queue` bridges the WebSocket receiver and the TTS task.
- `speak_task = asyncio.create_task(tts.speak_stream(chunker, player, token_queue))` runs concurrently.
- WebSocket events are consumed in a loop:
  - `stream_token` → put `("stream_token", content)` on queue; check barge-in.
  - `stream_end` / `assistant_message` → drain queue with `None` sentinel, break.
  - `error` → log, put sentinel, break.
- `await speak_task` at the end ensures audio finishes before returning to IDLE.

### Barge-In

```python
def _check_barge_in(self) -> bool:
    return self._mic.get_rms(window_ms=200) > self._cfg.barge_in_threshold
```

Called on every `stream_token` event during SPEAKING. If it fires:
1. `self._player.stop()` — interrupts TTS playback immediately.
2. `token_queue.put(None)` — cancels the TTS task.
3. Re-enters `collect_utterance` → `transcribe` → `_handle_response` recursively.

### Model Pin — Memory Safety

`VoiceClient` always sends `"use_reasoning": False`. This prevents the orchestrator from routing to `deepseek-r1:1.5b` (reasoning path) or the heavy `gemma4:e2b-it-q4_K_M` (7.2 GB). Ollama will serve `llama3.2` (2.0 GB) which is the lightest available text model and fast enough for conversational turns.

| Model | Size | Used in voice? |
|---|---|---|
| `llama3.2` | 2.0 GB | ✅ Yes (default) |
| `deepseek-r1:1.5b` | 1.1 GB | ❌ No (`use_reasoning=False`) |
| `qwen2.5:7b` | 4.7 GB | ❌ No (fallback, not triggered) |
| `gemma4:e2b-it-q4_K_M` | 7.2 GB | ❌ No (would kill RAM) |

---

## `voice.py` — CLI Entry Point (project root)

```python
#!/usr/bin/env python3
"""RAGenie Voice Assistant — say the wake phrase to begin."""
import asyncio
import argparse
from src.config.loader import load_config
from src.voice.voice_client import VoiceClient


def parse_args():
    p = argparse.ArgumentParser(description="RAGenie Voice Assistant")
    p.add_argument("--ws-url", default=None, help="WebSocket URL (default: from config)")
    p.add_argument("--model-size", default=None, choices=["tiny", "base", "small"])
    p.add_argument("--voice", default=None, help="edge-tts voice name")
    p.add_argument("--wake-word", default=None, help="openWakeWord phrase")
    p.add_argument("--threshold", type=float, default=None)
    return p.parse_args()


def main():
    args = parse_args()
    config = load_config()

    # CLI overrides
    if args.model_size:
        config.voice.stt.model_size = args.model_size
    if args.voice:
        config.voice.tts.voice = args.voice
    if args.wake_word:
        config.voice.wake_word.phrase = args.wake_word
    if args.threshold is not None:
        config.voice.wake_word.threshold = args.threshold

    ws_url = args.ws_url or (
        f"ws://{config.server.host}:{config.server.port}/ws/chat/voice-session"
    )

    client = VoiceClient(config.voice, ws_url)
    asyncio.run(client.run())


if __name__ == "__main__":
    main()
```

---

## Tests (`tests/test_voice_client.py`)

```python
async def test_idle_to_listening_on_wake(mock_wake_engine, mock_mic):
    """State transitions IDLE → LISTENING when wake word fires."""
    client = VoiceClient(VoiceConfig(), ws_url="ws://localhost:8000/ws/chat/test")
    client._wake = mock_wake_engine
    client._mic = mock_mic
    mock_wake_engine.process_chunk.return_value = True
    mock_mic.read_chunk.return_value = np.zeros(1280, dtype=np.float32)

    with patch.object(client, "_handle_response", new_callable=AsyncMock):
        with patch.object(client._stt, "collect_utterance", return_value=np.zeros(8000)):
            with patch.object(client._stt, "transcribe", return_value="hello"):
                await client._step()

    assert client._state == VoiceState.IDLE  # full cycle completed back to IDLE

async def test_empty_transcript_returns_to_idle(mock_wake_engine, mock_mic, mock_stt):
    """Empty STT result → no WebSocket call → back to IDLE."""
    client = VoiceClient(VoiceConfig(), ws_url="ws://localhost:8000/ws/chat/test")
    client._state = VoiceState.LISTENING
    mock_stt.collect_utterance.return_value = np.zeros(8000)
    mock_stt.transcribe.return_value = ""
    client._stt = mock_stt

    await client._step()
    assert client._state == VoiceState.IDLE

async def test_barge_in_stops_player(mock_mic):
    """High RMS during SPEAKING triggers barge-in."""
    config = VoiceConfig(barge_in_threshold=0.01)
    client = VoiceClient(config, ws_url="ws://localhost:8000/ws/chat/test")
    mock_mic.get_rms.return_value = 0.05  # above threshold
    client._mic = mock_mic
    assert client._check_barge_in() is True
```
