# Spec: wake-word

## Purpose

Continuously monitor microphone input for the configured wake phrase using `openWakeWord`. When detected above the configured confidence threshold, signal the voice pipeline to begin recording the user's utterance.

## Module

- `src/voice/wake_word.py`

---

## `WakeWordEngine`

```python
class WakeWordEngine:
    def __init__(self, model_path: Optional[str], phrase: str, threshold: float)
    def process_chunk(self, audio: np.ndarray) -> bool
    def reset(self) -> None
    def close(self) -> None
```

### `__init__`

```python
import openwakeword
from openwakeword.model import Model as OWWModel

def __init__(self, model_path: Optional[str], phrase: str, threshold: float):
    if model_path and os.path.exists(model_path):
        self._model = OWWModel(wakeword_models=[model_path])
        self._model_key = os.path.splitext(os.path.basename(model_path))[0]
    else:
        self._model = OWWModel(wakeword_models=[phrase])
        self._model_key = phrase
    self._threshold = threshold
    self._cooldown_frames = 0
```

- If `model_path` is set and the file exists, load a custom ONNX model.
- Otherwise, use the `phrase` string as a key to load the bundled pretrained openWakeWord model (e.g. `"hey_jarvis"`).
- `_model_key`: used to index `model.predict()` results dict.

### `process_chunk(audio: np.ndarray) -> bool`

```python
def process_chunk(self, audio: np.ndarray) -> bool:
    if self._cooldown_frames > 0:
        self._cooldown_frames -= 1
        return False
    prediction = self._model.predict(audio)
    score = prediction.get(self._model_key, 0.0)
    if score >= self._threshold:
        self._cooldown_frames = 48  # ~3s cooldown at 16kHz/1024-frame chunks
        return True
    return False
```

- `audio`: 1280-sample float32 array at 16kHz (80ms chunk — openWakeWord's expected chunk size).
- Returns `True` exactly once per wake event; subsequent calls suppressed for `cooldown_frames` to prevent double-triggers.
- Cooldown of 48 chunks × 80ms ≈ 3.8 s — prevents the wake phrase in the response from retriggering.

### `reset()`

Clear accumulated openWakeWord internal state. Called after a voice session completes to reset prediction context.

```python
def reset(self) -> None:
    self._model.reset()
    self._cooldown_frames = 0
```

### `close()`

Release model resources.

---

## Ring Buffer Strategy

`WakeWordEngine` is fed audio by `VoiceClient` from a continuously running `MicCapture`. The mic runs at 16kHz, producing 1280-sample chunks (80ms). These are fed directly to `process_chunk` in a tight loop:

```python
while state == IDLE:
    chunk = mic.read_chunk(1280)
    if wake_engine.process_chunk(chunk):
        state = LISTENING
        wake_engine.reset()
        play_activation_beep()
        break
```

No ring buffer is needed for wake word detection — `openWakeWord` maintains its own internal sliding context window.

---

## openWakeWord Pretrained Models

`openWakeWord` ships these pretrained models (downloadable via `openwakeword.utils.download_models()`):

| Model Key | Phrase |
|---|---|
| `hey_jarvis` | "Hey Jarvis" |
| `alexa` | "Alexa" |
| `hey_mycroft` | "Hey Mycroft" |
| `hey_rhasspy` | "Hey Rhasspy" |

**For v1:** Use `hey_jarvis` as it phonetically resembles "Hey RAGenie" well enough for testing.

**For custom "Hey RAGenie":** See `tasks.md` Phase 8. Requires recording audio examples and fine-tuning the `openWakeWord` feature extractor using their `train.py` script.

---

## Activation Beep

On successful wake word detection, play a short beep to give auditory confirmation:

```python
def play_activation_beep() -> None:
    import numpy as np
    import sounddevice as sd
    t = np.linspace(0, 0.15, int(16000 * 0.15))
    beep = 0.3 * np.sin(2 * np.pi * 880 * t).astype(np.float32)
    sd.play(beep, samplerate=16000, blocking=True)
```

Pure sine wave at 880 Hz for 150 ms — no external audio file required.

---

## Tests (`tests/test_voice_wake_word.py`)

### Unit Tests

```python
def test_wake_word_detects_above_threshold(mock_oww_model):
    engine = WakeWordEngine(model_path=None, phrase="hey_jarvis", threshold=0.5)
    mock_oww_model.predict.return_value = {"hey_jarvis": 0.85}
    assert engine.process_chunk(np.zeros(1280, dtype=np.float32)) is True

def test_wake_word_ignores_below_threshold(mock_oww_model):
    engine = WakeWordEngine(model_path=None, phrase="hey_jarvis", threshold=0.5)
    mock_oww_model.predict.return_value = {"hey_jarvis": 0.3}
    assert engine.process_chunk(np.zeros(1280, dtype=np.float32)) is False

def test_cooldown_prevents_double_trigger(mock_oww_model):
    engine = WakeWordEngine(model_path=None, phrase="hey_jarvis", threshold=0.5)
    mock_oww_model.predict.return_value = {"hey_jarvis": 0.9}
    assert engine.process_chunk(np.zeros(1280)) is True   # fires
    assert engine.process_chunk(np.zeros(1280)) is False  # suppressed by cooldown

def test_reset_clears_cooldown(mock_oww_model):
    engine = WakeWordEngine(model_path=None, phrase="hey_jarvis", threshold=0.5)
    mock_oww_model.predict.return_value = {"hey_jarvis": 0.9}
    engine.process_chunk(np.zeros(1280))  # trigger cooldown
    engine.reset()
    assert engine.process_chunk(np.zeros(1280)) is True  # fires again after reset

def test_custom_model_path_loaded(tmp_path, mock_oww_model_class):
    model_file = tmp_path / "hey_ragenie.onnx"
    model_file.touch()
    engine = WakeWordEngine(model_path=str(model_file), phrase="hey_ragenie", threshold=0.5)
    mock_oww_model_class.assert_called_with(wakeword_models=[str(model_file)])
```
