# Voice Assistant — Design Document

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                   voice.py  (entry point)                    │
│                                                              │
│   python voice.py [--model base] [--voice en-US-JennyNeural]│
└───────────────────────────┬──────────────────────────────────┘
                            │ starts
                            ▼
┌──────────────────────────────────────────────────────────────┐
│              VoiceClient  (src/voice/voice_client.py)        │
│                                                              │
│  ┌─────────────────┐   wake   ┌──────────────────────────┐  │
│  │  WakeWordEngine  ├─────────►  AudioCapture (sounddevice│  │
│  │ (openWakeWord)  │          │  + silero-vad)            │  │
│  │                 │          └────────────┬─────────────┘  │
│  │  ring buffer    │                       │ raw audio       │
│  │  16kHz float32  │                       ▼                 │
│  └─────────────────┘          ┌──────────────────────────┐  │
│                               │  STTEngine (faster-whisper│  │
│                               │  base, CoreML on M3)      │  │
│                               └────────────┬─────────────┘  │
│                                            │ text            │
│                                            ▼                 │
│                               ┌──────────────────────────┐  │
│                               │  WSAgentClient           │  │
│                               │  ws://localhost:8000/    │  │
│                               │  ws/chat                 │  │
│                               │                          │  │
│                               │  sends:                  │  │
│                               │  { message, use_agent,   │  │
│                               │    conversation_id,      │  │
│                               │    voice_model: llama3.2}│  │
│                               └────────────┬─────────────┘  │
│                                            │ stream_token /  │
│                                            │ assistant_msg   │
│                                            ▼                 │
│                               ┌──────────────────────────┐  │
│                               │  TTSEngine (edge-tts)    │  │
│                               │  + SentenceChunker       │  │
│                               │  + AudioPlayer           │  │
│                               │  (sounddevice + asyncio) │  │
│                               └──────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                            │
                            │ existing WebSocket (unchanged)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│               RAGenie FastAPI Backend (existing)             │
│                                                              │
│   websocket.py → orchestrator.achat() → llama3.2 via Ollama │
└──────────────────────────────────────────────────────────────┘
```

## Pipeline State Machine

```
IDLE
  │   wake word detected
  ▼
LISTENING
  │   VAD silence > 800ms (end of utterance)
  ▼
TRANSCRIBING
  │   faster-whisper returns text
  ▼
WAITING_RESPONSE
  │   WebSocket stream_token arrives
  ▼
SPEAKING          ◄──── barge-in: if new audio energy > threshold
  │   TTS audio complete                │
  ▼                                     │
IDLE ◄────────────────────────────────── LISTENING (restart)
```

## Module Breakdown

### New Package: `src/voice/`

| File | Responsibility |
|---|---|
| `__init__.py` | Package exports |
| `wake_word.py` | `WakeWordEngine` — openWakeWord loop on ring buffer |
| `stt.py` | `STTEngine` — VAD silence detection + faster-whisper transcription |
| `tts.py` | `TTSEngine` — edge-tts synthesis, sentence chunker, async audio queue |
| `audio_io.py` | `MicCapture` + `AudioPlayer` — sounddevice wrappers |
| `voice_client.py` | `VoiceClient` — state machine, WebSocket client, pipeline orchestration |

### Entry Point

| File | Responsibility |
|---|---|
| `voice.py` (project root) | CLI entry — loads config, starts `VoiceClient` async loop |

### Config Extension

| File | Change |
|---|---|
| `src/config/models.py` | Add `VoiceSTTConfig`, `VoiceTTSConfig`, `VoiceConfig` Pydantic models |
| `config/config.yaml` | Add `voice:` top-level block |

### No Backend Changes Required

The voice client is a **standalone asyncio process**. It connects to the existing WebSocket endpoint `ws://localhost:8000/ws/chat` using `websockets` (already in `requirements.txt`). No changes to `websocket.py`, `orchestrator.py`, or `app.py` are needed for v1.

The only backend interaction is an optional model-pin header or `conversation_id` prefix (`voice-{uuid}`) to keep voice conversations separate in the DB.

---

## Key Design Decisions

### 1. Model Pinning for Voice Mode

Voice mode always uses `llama3.2` (2.0 GB) regardless of the `multi_model` config. This is enforced client-side: `VoiceClient` sends a `conversation_id` prefixed with `"voice-"`. A future backend guard could reject model overrides, but for v1 the client-side contract is sufficient because the voice client itself sends no `use_reasoning` flag.

### 2. Sentence-Streaming TTS

The WebSocket sends `stream_token` events token by token. `SentenceChunker` accumulates tokens and fires TTS synthesis when it detects a sentence boundary (`.`, `?`, `!`, `\n`) or when the buffer exceeds 120 characters. This delivers the first spoken word typically within 1.5–2 s of the LLM starting to generate on M3 hardware.

```
stream_token("The ")
stream_token("weather ")
stream_token("in ")
stream_token("Bangalore ")
stream_token("is ")
stream_token("28°C.")    ← boundary → synthesize "The weather in Bangalore is 28°C."
stream_token(" It ")
stream_token("is ")
stream_token("humid.")   ← boundary → synthesize "It is humid."
```

### 3. Barge-In Detection

`MicCapture` runs continuously in a background thread even during TTS playback. If RMS energy in a 200 ms window exceeds `barge_in_threshold` (configurable, default `0.015`), `AudioPlayer.stop()` is called and the state machine transitions to `LISTENING`. This prevents the user from having to wait for RAGenie to finish speaking.

### 4. VAD Strategy

Two-pass VAD:
1. **Energy gate**: discard frames below `vad_energy_threshold` to avoid transcribing silence/background noise.
2. **Silero VAD**: run on 512-sample chunks at 16 kHz; accumulate speech frames until Silero detects 800 ms consecutive silence — that's the utterance boundary.

Silero VAD is preferred over `webrtcvad` because it's more accurate in noisy environments and runs as a lightweight ONNX model (~1 MB) with no additional install complexity.

### 5. Wake Word Model

`openWakeWord` ships with pre-trained models for several phrases. The closest available is `"hey_jarvis"`. For v1, this is used as a placeholder. A custom `"hey_ragenie"` wake word requires recording ~150 positive examples and fine-tuning the model — this is documented as a post-v1 task. The phrase can be configured in `config.yaml` so swapping the model file requires no code change.

### 6. TTS Engine Choice

| Engine | Offline | Quality | RAM | Chosen? |
|---|---|---|---|---|
| `edge-tts` | No (HTTPS) | Excellent (neural) | ~0 MB | ✅ v1 |
| `kokoro-onnx` | Yes | Very good | ~300 MB | v2 option |
| `pyttsx3` / macOS `say` | Yes | Poor (robotic) | ~0 MB | fallback only |
| `coqui-tts` | Yes | Good | 1–2 GB | Too heavy |
| OpenAI TTS | No | Excellent | ~0 MB | Requires paid API key |

`edge-tts` is selected for v1: it requires no API key, no local model, produces near-Siri quality output, and uses ~0 RAM. The only downside is network dependency — a `pyttsx3` fallback is included for offline use.

---

## Dependency Additions to `requirements.txt`

```
# Voice Assistant
openwakeword>=0.6.0          # wake word detection
faster-whisper>=1.0.0        # speech-to-text (CoreML on Apple Silicon)
edge-tts>=6.1.9              # TTS via Microsoft Edge neural voices (no API key)
sounddevice>=0.4.6           # microphone capture + audio playback
silero-vad>=5.1.0            # voice activity detection
onnxruntime>=1.18.0          # required by both openWakeWord and silero-vad
pyttsx3>=2.90                # offline TTS fallback (uses macOS built-in voices)
```

**Note:** `scipy` (for audio resampling) and `websockets` (for WS client) are already present.

---

## Audio Format Flow

```
Microphone  →  sounddevice (float32, 16kHz, mono)
                   │
                   ├── openWakeWord: requires 16kHz float32 ✓
                   │
                   └── Silero VAD: requires 16kHz int16 → resampled with numpy
                                        │
                                        └── faster-whisper: requires 16kHz float32 ✓

TTS output  →  edge-tts returns MP3 bytes
                   │
                   └── sounddevice playback: decode MP3 → PCM via soundfile/scipy ✓
```
