# Spec: voice-config

## Purpose

Define the Pydantic config models for the voice assistant and the corresponding `config.yaml` additions. All voice pipeline parameters are grouped under a single `voice:` top-level key, consistent with existing config sections (`llm`, `rag`, `memory`, etc.).

## Modules

- `src/config/models.py` (modified — add 4 new models + 1 field on root `Config`)
- `config/config.yaml` (modified — add `voice:` block)
- `requirements.txt` (modified — add 7 new packages)

---

## Config Models (`src/config/models.py`)

### `VoiceWakeWordConfig`

```python
class VoiceWakeWordConfig(BaseModel):
    phrase: str = Field(default="hey_jarvis")
    model_path: Optional[str] = Field(default=None)
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
```

- `phrase`: human-readable name used for logging only.
- `model_path`: path to a custom `.onnx` wake word model. `None` means use the `phrase` name to look up a bundled openWakeWord model.
- `threshold`: confidence score required to trigger wake (0.0–1.0). Higher = fewer false positives.

### `VoiceSTTConfig`

```python
class VoiceSTTConfig(BaseModel):
    engine: str = Field(default="faster-whisper")
    model_size: str = Field(default="base")
    language: str = Field(default="en")
    device: str = Field(default="cpu")
    compute_type: str = Field(default="int8")
```

- `engine`: only `"faster-whisper"` is supported in v1.
- `model_size`: `"tiny"` (~40 MB), `"base"` (~150 MB), `"small"` (~500 MB). Use `"base"` on M3 Air 16 GB.
- `device`: `"cpu"` on Apple Silicon (faster-whisper uses CoreML acceleration automatically under `"cpu"`).
- `compute_type`: `"int8"` for quantised inference on CPU; reduces RAM by ~40%.

### `VoiceTTSConfig`

```python
class VoiceTTSConfig(BaseModel):
    engine: str = Field(default="edge-tts")
    voice: str = Field(default="en-US-JennyNeural")
    rate: str = Field(default="+0%")
    fallback_engine: str = Field(default="pyttsx3")
```

- `engine`: `"edge-tts"` (primary) or `"pyttsx3"` (offline fallback).
- `voice`: Microsoft Edge TTS voice name. Full list: `python -m edge_tts --list-voices`.
  - Natural English options: `en-US-JennyNeural`, `en-US-GuyNeural`, `en-IN-NeerjaNeural` (Indian accent).
- `rate`: speech rate adjustment. `"+10%"` = 10% faster, `"-10%"` = slower.
- `fallback_engine`: used when `edge-tts` is unreachable (no internet / network error).

### `VoiceConfig`

```python
class VoiceConfig(BaseModel):
    enabled: bool = Field(default=False)
    wake_word: VoiceWakeWordConfig = Field(default_factory=VoiceWakeWordConfig)
    stt: VoiceSTTConfig = Field(default_factory=VoiceSTTConfig)
    tts: VoiceTTSConfig = Field(default_factory=VoiceTTSConfig)
    vad_silence_ms: int = Field(default=800, ge=200, le=3000)
    barge_in_threshold: float = Field(default=0.015, ge=0.0, le=1.0)
    llm_model: str = Field(default="llama3.2")
    use_agent: bool = Field(default=True)
    conversation_id_prefix: str = Field(default="voice")
```

- `vad_silence_ms`: milliseconds of consecutive silence to consider the utterance complete. 800 ms is a natural pause length; increase to 1200 ms for deliberate speakers.
- `barge_in_threshold`: RMS energy level that triggers barge-in (interrupt TTS). 0.015 works for most quiet rooms; lower in noisy environments.
- `llm_model`: Ollama model name for voice sessions. **Always use `llama3.2`** (2.0 GB) to avoid loading heavy models during voice mode. Do not set to `qwen2.5:7b` (4.7 GB) or `gemma4:e2b` (7.2 GB).
- `use_agent`: `True` enables tool use (RAG search, web search). Set `False` for lowest latency (pure LLM chat).
- `conversation_id_prefix`: voice sessions use IDs like `"voice-abc123"` to keep them separate from text chat history in the DB.

### Root Config Addition

```python
class Config(BaseModel):
    # ... existing fields ...
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
```

---

## config.yaml Addition

```yaml
# Voice Assistant Configuration
# Activate with: python voice.py
# Requires: pip install openwakeword faster-whisper edge-tts sounddevice silero-vad onnxruntime pyttsx3
voice:
  enabled: false

  wake_word:
    phrase: "hey_jarvis"           # v1 placeholder — see tasks.md Phase 8 for custom "hey_ragenie"
    model_path: null               # null = use bundled openWakeWord model for 'phrase'
    threshold: 0.5                 # confidence threshold (0.0–1.0)

  stt:
    engine: "faster-whisper"
    model_size: "base"             # tiny (~40MB) | base (~150MB) | small (~500MB)
    language: "en"
    device: "cpu"                  # CoreML-accelerated on Apple Silicon despite 'cpu' label
    compute_type: "int8"           # quantised — reduces RAM ~40%

  tts:
    engine: "edge-tts"             # primary: Microsoft Edge neural TTS (no API key, free)
    voice: "en-US-JennyNeural"     # run: python -m edge_tts --list-voices
    rate: "+0%"
    fallback_engine: "pyttsx3"     # offline fallback using macOS built-in voices

  vad_silence_ms: 800              # ms of silence to end utterance
  barge_in_threshold: 0.015        # RMS energy to interrupt TTS playback
  llm_model: "llama3.2"           # IMPORTANT: keep as llama3.2 (2GB) to preserve RAM on M3
  use_agent: true                  # true = RAG + tool use; false = pure LLM (faster)
  conversation_id_prefix: "voice"
```

---

## requirements.txt Additions

```
# Voice Assistant
openwakeword>=0.6.0          # wake word detection (local, no API key)
faster-whisper>=1.0.0        # speech-to-text (CoreML-accelerated on Apple Silicon)
edge-tts>=6.1.9              # TTS via Microsoft Edge neural voices (free, no API key)
sounddevice>=0.4.6           # microphone capture + audio playback
silero-vad>=5.1.0            # voice activity detection
onnxruntime>=1.18.0          # ONNX runtime (used by openWakeWord + silero-vad)
pyttsx3>=2.90                # offline TTS fallback (uses macOS built-in voices)
```

**Note:** `scipy`, `numpy`, and `websockets` are already present and are also used by the voice pipeline.

---

## Tests (`tests/test_voice_config.py`)

- Load config with no `voice:` block → all fields use defaults (`enabled=False`)
- Load config with partial `voice:` block → unspecified fields use defaults
- Load config with invalid `threshold: 1.5` → Pydantic `ValidationError` raised
- Load config with invalid `model_size: "xxl"` → loaded without error (not enum-constrained; runtime check in `STTEngine`)
- Assert `config.voice.llm_model == "llama3.2"` default
