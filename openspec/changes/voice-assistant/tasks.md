# Voice Assistant — Implementation Tasks

## Phase 1: Config & Dependencies (Day 1)

### 1.1 Dependency Installation
- [x] Add to `requirements.txt`:
  ```
  openwakeword>=0.6.0
  faster-whisper>=1.0.0
  edge-tts>=6.1.9
  sounddevice>=0.4.6
  silero-vad>=5.1.0
  onnxruntime>=1.18.0
  pyttsx3>=2.90
  miniaudio>=1.57
  ```
- [x] Run `pip install openwakeword faster-whisper edge-tts sounddevice silero-vad onnxruntime pyttsx3`
- [x] Verify `import sounddevice` works and mic is detected: `python -c "import sounddevice; print(sounddevice.query_devices())"`
- [x] Download openWakeWord pretrained models: `python -c "import openwakeword; openwakeword.utils.download_models()"`
- [x] Download faster-whisper base model: `python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"`

### 1.2 Config Model
- [x] Add to `src/config/models.py`:
  - `VoiceSTTConfig(BaseModel)` with fields: `engine`, `model_size`, `language`, `device`
  - `VoiceTTSConfig(BaseModel)` with fields: `engine`, `voice`, `rate`, `fallback_engine`
  - `VoiceWakeWordConfig(BaseModel)` with fields: `phrase`, `model_path`, `threshold`
  - `VoiceConfig(BaseModel)` with fields: `enabled`, `wake_word`, `stt`, `tts`, `vad_silence_ms`, `barge_in_threshold`, `llm_model`, `use_agent`, `conversation_id_prefix`
  - Add `voice: VoiceConfig` field to root `Config` model
- [x] Add `voice:` block to `config/config.yaml` (see spec: `voice-config`)
- [x] Write unit test: `tests/test_voice_config.py` — verify config loads with defaults

---

## Phase 2: Audio I/O Layer (Day 1–2)

### 2.1 Mic Capture (`src/voice/audio_io.py`)
- [x] Implement `MicCapture` class:
  - `start()` — opens sounddevice InputStream at 16kHz, mono, float32
  - `stop()` — closes stream
  - `read_chunk(n_frames) -> np.ndarray` — non-blocking read from ring buffer
  - `get_rms() -> float` — RMS energy of last 200ms (barge-in detection)
- [x] Implement `AudioPlayer` class:
  - `play_mp3_bytes(audio_bytes: bytes) -> None` — primary: afplay (macOS, zero deps); fallback: decode MP3 → PCM via miniaudio, play via sounddevice
  - `stop()` — interrupt playback immediately (for barge-in)
  - `is_playing() -> bool`
- [x] Test manually: record 3 s of audio, play it back

### 2.2 Package Scaffold
- [x] Create `src/voice/__init__.py`
- [x] Create: `wake_word.py`, `stt.py`, `tts.py`, `voice_client.py`, `audio_io.py`, `overlay.py`, `state_bridge.py`

---

## Phase 3: Wake Word Detection (Day 2)

### 3.1 WakeWordEngine (`src/voice/wake_word.py`)
- [x] Implement `WakeWordEngine`:
  - `__init__(model_path: str, threshold: float)` — load openWakeWord model
  - `process_chunk(audio: np.ndarray, threshold=None) -> bool` — returns True if wake word detected above threshold; optional override for interrupt detection (0.30)
  - `reset()` — clear internal state after activation
- [x] Use `openwakeword.Model(wakeword_models=[model_path])` for multi-phrase support
- [x] Default model: `"hey_jarvis"` (v1 placeholder) — configurable via `voice.wake_word.model_path`
- [x] Write test: `tests/test_voice_wake_word.py` — mock audio chunks, verify detection fires at threshold
- [x] Manual test: say "Hey Jarvis" → confirmed wake beep fires, session transitions to LISTENING

---

## Phase 4: STT + VAD (Day 2–3)

### 4.1 STTEngine (`src/voice/stt.py`)
- [x] Implement `STTEngine`:
  - `__init__(config: VoiceSTTConfig)` — load `WhisperModel(model_size, device="cpu", compute_type="int8")` (CoreML-accelerated on M3 via `faster-whisper`)
  - `transcribe(audio: np.ndarray) -> str` — run `model.transcribe(audio, language=language)`, return joined text
  - Audio input: 16kHz float32 numpy array
- [x] Implement `SileroVAD` in `stt.py`:
  - Load `silero-vad` via PyPI; falls back to energy-based VAD if unavailable
  - `is_speech(chunk: np.ndarray) -> bool` — returns True for speech frames
  - `collect_utterance(mic: MicCapture, silence_ms: int) -> np.ndarray` — accumulate speech until `silence_ms` of consecutive silence detected; return full utterance array
- [x] Write test: `tests/test_voice_stt.py` — mock faster-whisper and silero-vad; verify transcript joining, error handling, collect_utterance behaviour

---

## Phase 5: TTS Engine (Day 3)

### 5.1 TTSEngine (`src/voice/tts.py`)
- [x] Implement `SentenceChunker`:
  - `feed(token: str) -> List[str]` — append token to buffer; return complete sentences on `.?!` boundaries
  - `drain() -> str` — return remaining buffer content (called on `stream_end`)
  - `MAX_BUFFER_CHARS = 120` — forces flush for very long run-on sentences
- [x] Implement `TTSEngine`:
  - `__init__(config: VoiceTTSConfig)`
  - `async synthesize(text: str) -> Optional[bytes]` — call `edge_tts.Communicate(text, voice).stream()`, collect MP3 bytes; returns None on failure
  - `async speak(text: str, player: AudioPlayer)` — synthesize then play; pyttsx3 fallback if edge-tts returns None
  - `async speak_stream(chunker, player, token_queue)` — sentence-streaming from async queue
- [x] Write test: `tests/test_voice_tts.py` — mock `edge_tts.Communicate`, verify bytes returned; test all SentenceChunker boundary cases

---

## Phase 6: Voice Client Orchestrator (Day 4)

### 6.1 VoiceClient (`src/voice/voice_client.py`)
- [x] Implement state machine enum: `VoiceState(IDLE, LISTENING, TRANSCRIBING, WAITING_RESPONSE, SPEAKING)`
- [x] Implement `VoiceClient`:
  - `__init__(config: VoiceConfig, ws_url: str)` — instantiate all sub-engines
  - `async run()` — main loop with full state transitions
  - `_watch_for_wake_interrupt()` — background task using INTERRUPT_THRESHOLD=0.30 during SPEAKING
  - WebSocket retry logic (MAX_RETRIES=3, RETRY_DELAY=4s) with TTS spoken feedback on connection failures
  - WebSocket message: `{"message": text, "conversation_id": ..., "use_agent": ..., "use_reasoning": false}`
- [x] Write integration test: `tests/test_voice_client.py` — mock all sub-engines, verify state transitions

### 6.2 Entry Point
- [x] Create `voice.py` at project root:
  - Parse CLI args: `--ws-url`, `--model-size`, `--voice`, `--wake-word`, `--threshold`
  - Load config from `config/config.yaml`
  - Instantiate `VoiceClient(config.voice, ws_url)`
  - Run `asyncio.run(client.run())`
  - Handle `KeyboardInterrupt` + `SIGTERM` gracefully
- [x] `python voice.py --help` — verified working

---

## Phase 7: Integration & Manual Testing (Day 5)

### 7.1 End-to-End Test
- [x] Start RAGenie server: `./start.sh` (backend + frontend + voice + overlay all in one)
- [x] Say "Hey Jarvis" → confirmed 660 Hz chime fires, session transitions to LISTENING
- [x] Say "Tell me a joke" → transcript printed, response streamed from RAGenie
- [x] Hear response spoken aloud via edge-tts (en-US-JennyNeural)
- [x] Test barge-in: saying wake phrase mid-response stops TTS and starts new listen session

### 7.2 Memory Check
- [x] Verified via Activity Monitor: RAGenie backend + Ollama (llama3.2) + voice client stays well under 10 GB on M3 16 GB
- [x] Confirmed Ollama loads `llama3.2` (use_reasoning=False always set in VoiceClient)

### 7.3 Latency Measurement (observed on M3 MacBook Air)
- [x] VAD silence detection: ~200–400 ms
- [x] faster-whisper base transcription: ~300–600 ms
- [x] LLM first token (llama3.2 via Ollama): ~400–800 ms
- [x] edge-tts synthesis of first sentence: ~300–500 ms
- [x] **Observed end-to-end: ~1.5–2.5 s** — within target

---

## Phase 8: Custom Wake Word (Post-v1, Optional)

### 8.1 Record Training Data
- [ ] Record 150+ positive examples of "Hey RAGenie" (various speeds, accents)
- [ ] Record 500+ negative examples (ambient noise, other phrases)
- [ ] Use `openWakeWord` training script to fine-tune on custom phrase
- [ ] Save model to `data/voice/hey_ragenie.onnx`
- [ ] Update `config.yaml`: `voice.wake_word.model_path: "data/voice/hey_ragenie.onnx"`

> **Status**: Deferred to post-v1. Current "hey_jarvis" placeholder works reliably.
> See `openspec/changes/voice-assistant/specs/wake-word/spec.md` for training details.

---

## Checklist Summary

| Phase | Files Created/Modified | Status |
|---|---|---|
| 1 | `requirements.txt`, `src/config/models.py`, `config/config.yaml` | [x] |
| 2 | `src/voice/__init__.py`, `src/voice/audio_io.py` | [x] |
| 3 | `src/voice/wake_word.py`, `tests/test_voice_wake_word.py` | [x] |
| 4 | `src/voice/stt.py`, `tests/test_voice_stt.py` | [x] |
| 5 | `src/voice/tts.py`, `tests/test_voice_tts.py` | [x] |
| 6 | `src/voice/voice_client.py`, `voice.py`, `tests/test_voice_client.py` | [x] |
| 7 | Manual integration test + latency measurement | [x] |
| 8 | Custom wake word training (post-v1) | [ ] deferred |
