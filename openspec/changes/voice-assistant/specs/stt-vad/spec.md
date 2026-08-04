# Spec: stt-vad

## Purpose

After wake word detection, capture the user's spoken utterance by:
1. Detecting speech onset and offset using Silero VAD.
2. Collecting continuous audio until a configurable silence window elapses.
3. Transcribing the collected audio to text using `faster-whisper`.

## Module

- `src/voice/stt.py`

---

## Classes

### `SileroVAD`

```python
class SileroVAD:
    def __init__(self)
    def is_speech(self, chunk: np.ndarray, sample_rate: int = 16000) -> bool
```

**Init:**
Load Silero VAD ONNX model via `torch.hub`:

```python
import torch
model, utils = torch.hub.load(
    repo_or_dir="snakers4/silero-vad",
    model="silero_vad",
    force_reload=False,
    onnx=True,
)
self._model = model
self._get_speech_ts = utils[0]  # get_speech_timestamps
self._h = torch.zeros(2, 1, 64)
self._c = torch.zeros(2, 1, 64)
```

**`is_speech(chunk, sample_rate) -> bool`:**

```python
def is_speech(self, chunk: np.ndarray, sample_rate: int = 16000) -> bool:
    audio_tensor = torch.from_numpy(chunk).unsqueeze(0)
    with torch.no_grad():
        out, self._h, self._c = self._model(audio_tensor, self._h, self._c)
    return out.item() > 0.5
```

- `chunk`: 512-sample float32 array (32ms at 16kHz) — Silero's required chunk size.
- Returns `True` if the probability of speech exceeds 0.5.
- Hidden states `_h`, `_c` are maintained across calls so the model has temporal context.

---

### `STTEngine`

```python
class STTEngine:
    def __init__(self, config: VoiceSTTConfig)
    def transcribe(self, audio: np.ndarray) -> str
    def collect_utterance(self, mic: "MicCapture", silence_ms: int) -> np.ndarray
```

**`__init__`:**

```python
from faster_whisper import WhisperModel

def __init__(self, config: VoiceSTTConfig):
    self._model = WhisperModel(
        config.model_size,
        device=config.device,       # "cpu" → faster-whisper auto-detects CoreML on M3
        compute_type=config.compute_type,
    )
    self._language = config.language
    self._vad = SileroVAD()
```

**`transcribe(audio: np.ndarray) -> str`:**

```python
def transcribe(self, audio: np.ndarray) -> str:
    segments, _info = self._model.transcribe(
        audio,
        language=self._language,
        beam_size=3,
        vad_filter=True,           # built-in faster-whisper VAD pre-filtering
    )
    return " ".join(seg.text.strip() for seg in segments).strip()
```

- `vad_filter=True` enables faster-whisper's internal VAD to remove silence from the audio before transcription, reducing hallucinations on silent audio.
- `beam_size=3` balances accuracy vs. speed on CPU.

**`collect_utterance(mic: MicCapture, silence_ms: int) -> np.ndarray`:**

```python
def collect_utterance(self, mic: MicCapture, silence_ms: int) -> np.ndarray:
    CHUNK_SAMPLES = 512         # 32ms at 16kHz (Silero's required chunk size)
    silence_chunks = silence_ms // 32  # convert ms to chunk count
    
    speech_frames: List[np.ndarray] = []
    consecutive_silence = 0
    started = False
    
    while True:
        chunk = mic.read_chunk(CHUNK_SAMPLES)
        if self._vad.is_speech(chunk):
            started = True
            consecutive_silence = 0
            speech_frames.append(chunk)
        elif started:
            consecutive_silence += 1
            speech_frames.append(chunk)  # include trailing silence for natural transcription
            if consecutive_silence >= silence_chunks:
                break
        # if not started yet, keep waiting (discard pre-speech silence)
    
    return np.concatenate(speech_frames, axis=0)
```

- Does not start accumulating until first speech frame is detected (discards ambient noise before the user speaks).
- Includes trailing silence chunks so Whisper gets natural sentence endings.
- Returns when `silence_chunks` consecutive non-speech chunks occur after speech has started.

---

## Audio Format Requirements

| Stage | Sample Rate | Dtype | Channels |
|---|---|---|---|
| `MicCapture` output | 16kHz | float32 | mono |
| Silero VAD input | 16kHz | float32 | mono (512 samples/chunk) |
| faster-whisper input | 16kHz | float32 | mono (full utterance) |

All formats are consistent — no resampling required.

---

## Performance on M3 MacBook Air

| Whisper model size | RAM | M3 transcription time (5s audio) |
|---|---|---|
| `tiny` | ~40 MB | ~0.3 s |
| `base` | ~150 MB | ~0.5 s |
| `small` | ~500 MB | ~1.2 s |

**Recommended: `base`** — best accuracy/speed/RAM balance. `tiny` is acceptable if latency is critical.

faster-whisper automatically uses Apple CoreML acceleration on Apple Silicon when `device="cpu"` (it detects the hardware). No explicit CoreML configuration is needed.

---

## Tests (`tests/test_voice_stt.py`)

### SileroVAD Tests

```python
def test_silero_vad_detects_speech(mock_silero_model):
    vad = SileroVAD()
    mock_silero_model.return_value = (torch.tensor([[0.8]]), h, c)
    assert vad.is_speech(np.random.randn(512).astype(np.float32)) is True

def test_silero_vad_rejects_silence(mock_silero_model):
    vad = SileroVAD()
    mock_silero_model.return_value = (torch.tensor([[0.1]]), h, c)
    assert vad.is_speech(np.zeros(512, dtype=np.float32)) is False
```

### STTEngine Tests

```python
def test_transcribe_returns_text(wav_fixture_path):
    """Use a pre-recorded WAV file with known content."""
    import soundfile as sf
    audio, _ = sf.read(wav_fixture_path, dtype="float32")
    engine = STTEngine(VoiceSTTConfig())
    result = engine.transcribe(audio)
    assert "hello" in result.lower()

def test_collect_utterance_stops_on_silence(mock_mic, mock_vad):
    """Verify collection stops after configured silence threshold."""
    # First 10 chunks: speech, then 30 chunks: silence
    mock_vad.is_speech.side_effect = [True]*10 + [False]*30
    mock_mic.read_chunk.return_value = np.zeros(512, dtype=np.float32)
    engine = STTEngine(VoiceSTTConfig(model_size="base"))
    engine._vad = mock_vad
    audio = engine.collect_utterance(mock_mic, silence_ms=800)
    # 800ms / 32ms per chunk = 25 silence chunks needed
    assert audio.shape[0] == (10 + 25) * 512

def test_collect_utterance_ignores_leading_silence(mock_mic, mock_vad):
    """No frames collected until first speech frame detected."""
    mock_vad.is_speech.side_effect = [False]*5 + [True]*5 + [False]*30
    mock_mic.read_chunk.return_value = np.zeros(512, dtype=np.float32)
    engine = STTEngine(VoiceSTTConfig())
    engine._vad = mock_vad
    audio = engine.collect_utterance(mock_mic, silence_ms=800)
    # Only 5 speech + 25 silence chunks (not the 5 leading silence)
    assert audio.shape[0] == (5 + 25) * 512
```

### Test Fixture

Place `tests/fixtures/hello_world.wav` — a 16kHz mono WAV with someone saying "hello world" — for transcription accuracy tests. Generate it with:

```bash
python -c "
import numpy as np, soundfile as sf
# use edge-tts to generate fixture: python -m edge_tts --text 'hello world' --write-media tests/fixtures/hello_world.mp3
"
```
