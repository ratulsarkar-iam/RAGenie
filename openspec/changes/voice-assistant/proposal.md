# Voice Assistant for RAGenie — "Hey RAGenie"

## Overview

This proposal adds a fully local, wake-word-activated voice interface to RAGenie — similar to Siri, Alexa, or Google Assistant. The user says **"Hey RAGenie"**, speaks a prompt, hears the response spoken back, and the conversation continues hands-free.

## Problem Statement

RAGenie today is entirely text-driven. All interaction requires typing in the React frontend or a terminal. There is no:

- Wake-word listener that activates the agent on voice command.
- Microphone capture + speech-to-text (STT) pipeline.
- Text-to-speech (TTS) pipeline for spoken responses.
- Low-latency sentence-streaming TTS (don't wait for full LLM response before speaking).
- Barge-in detection (user can interrupt while RAGenie is speaking).
- Memory-aware model routing for voice mode on constrained hardware.

## Hardware & Model Constraints

**Target machine:** MacBook Air M3 16 GB unified memory.

**Memory budget (worst case, all running simultaneously):**

| Component | RAM |
|---|---|
| macOS + apps | ~4 GB |
| RAGenie FastAPI backend | ~600 MB |
| Ollama `llama3.2` (voice model) | ~2.0 GB |
| faster-whisper base (STT) | ~150 MB |
| openWakeWord (wake detector) | ~150 MB |
| edge-tts (TTS — HTTP, no local model) | ~0 MB |
| sounddevice + audio buffers | ~50 MB |
| **Total peak** | **~7 GB** |

This leaves ~9 GB headroom — safe on 16 GB. The **existing heavy models** (`gemma4:e2b-it-q4_K_M` at 7.2 GB, `qwen2.5:7b` at 4.7 GB) are **not loaded during voice mode**. Ollama unloads models from VRAM automatically between calls; voice mode always routes to `llama3.2`.

## Why Ollama Cannot Handle TTS

Ollama is a large language model runner — it generates text tokens. It has no audio encoder/decoder and produces no audio output. TTS requires a dedicated speech synthesis engine operating on waveform data. Ollama is **not a candidate for TTS** in this stack.

## Proposed Solution

A standalone Python voice client (`voice.py`) that:

1. **Runs continuously alongside the RAGenie server** as a separate process.
2. **Listens for the wake phrase** using `openWakeWord` (fully local, no API key, trainable for custom phrases).
3. **Records the user's speech** via `sounddevice` with `silero-vad` silence detection.
4. **Transcribes audio** using `faster-whisper` base model (CoreML-accelerated on Apple Silicon, ~150 MB).
5. **Sends the text** over the existing RAGenie WebSocket (`ws://localhost:8000/ws/chat`) using `use_agent=True` and forcing `llama3.2` for fast, low-memory responses.
6. **Reads the LLM reply aloud** sentence by sentence using `edge-tts` (Microsoft Edge TTS, free, no API key, natural voices) as tokens stream in — so the first sentence plays before the LLM finishes generating.
7. **Supports barge-in**: if the user starts speaking while TTS is playing, playback stops and the pipeline restarts from STT.

## Non-Goals

- Browser-based voice (Web Speech API) — separate future feature.
- Streaming audio transcription (real-time word-by-word STT) — batch per-utterance is sufficient.
- On-device TTS synthesis (`kokoro-onnx`, `coqui-tts`) — deferred to v2; `edge-tts` is better quality and zero memory cost.
- Multi-language wake word models — English only for v1.
- Integration into the React frontend UI — voice is a standalone client for v1.
- Voice authentication / speaker identification.

## Benefits

- **Zero-restart integration**: uses the existing WebSocket and agent unchanged.
- **Memory-safe**: voice mode pins `llama3.2`; heavy reasoning/main models are not loaded.
- **Fully offline STT + wake word**: no cloud dependency for listening; only TTS uses network (edge-tts).
- **Natural latency**: sentence-streaming TTS delivers sub-2s first-word latency on M3.
- **Extensible**: `src/voice/` package is independent — can later be wired into a REST endpoint or browser.

## Implementation Strategy

Five specs cover the full scope:

| Spec | What it covers |
|---|---|
| `voice-config` | Config model additions, `config.yaml` block, dependency list |
| `wake-word` | openWakeWord integration, audio ring buffer, activation threshold |
| `stt-vad` | Silero VAD silence detection, faster-whisper transcription |
| `tts` | edge-tts synthesis, async audio playback, sentence chunker, barge-in flag |
| `voice-client` | Top-level orchestrator, WebSocket client loop, model-pin routing, entry point `voice.py` |
