#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RAGenie Voice Assistant

Say the wake phrase to begin talking to RAGenie hands-free.

Usage:
    python voice.py
    python voice.py --model-size tiny
    python voice.py --voice en-IN-NeerjaNeural
    python voice.py --wake-word hey_jarvis --threshold 0.6
    python voice.py --no-agent                # skip RAG/tools, pure LLM (faster)

One-time setup (run once before first use):
    pip install openwakeword faster-whisper edge-tts sounddevice silero-vad onnxruntime pyttsx3
    python -c "import openwakeword; openwakeword.utils.download_models()"
    python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"

macOS note:
    If sounddevice fails with PortAudio error:  brew install portaudio
"""
import argparse
import asyncio
import logging
import os
import signal
import sys

sys.stdout.reconfigure(line_buffering=True)

os.makedirs("logs", exist_ok=True)

_log_file = "logs/voice.log"

# Technical logger (module-level, file only)
_file_handler = logging.FileHandler(_log_file)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s %(levelname)s %(name)s — %(message)s"
))
logging.basicConfig(level=logging.INFO, handlers=[_file_handler])
# Show wake word scores at DEBUG level for diagnosis
logging.getLogger("rag_chatbot.voice.wake_word").setLevel(logging.DEBUG)

# Conversation logger — readable entries in log file + clean terminal output
_conv_file = logging.FileHandler(_log_file)
_conv_file.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
_conv_stream = logging.StreamHandler(sys.stdout)
_conv_stream.setFormatter(logging.Formatter("%(message)s"))

_conv_log = logging.getLogger("voice.conv")
_conv_log.setLevel(logging.INFO)
_conv_log.addHandler(_conv_file)
_conv_log.addHandler(_conv_stream)
_conv_log.propagate = False  # don't double-write via root logger


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="RAGenie Voice Assistant — hands-free voice interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--ws-url",
        default=None,
        help="WebSocket base URL, e.g. ws://localhost:8000/ws (default: from config)",
    )
    p.add_argument(
        "--model-size",
        default=None,
        choices=["tiny", "base", "small"],
        help="faster-whisper model size (default: base ~150 MB)",
    )
    p.add_argument(
        "--voice",
        default=None,
        help="edge-tts voice name (default: en-US-JennyNeural). "
             "List available: python -m edge_tts --list-voices",
    )
    p.add_argument(
        "--wake-word",
        default=None,
        dest="wake_word",
        help="openWakeWord phrase/model key (default: hey_jarvis)",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Wake word confidence threshold 0.0–1.0 (default: 0.5)",
    )
    p.add_argument(
        "--no-agent",
        action="store_true",
        help="Disable agent/RAG — pure LLM mode, lower latency",
    )
    p.add_argument(
        "--silence-ms",
        type=int,
        default=None,
        dest="silence_ms",
        help="VAD silence window in ms to end utterance (default: 800)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from src.config.loader import load_config
        from src.voice.voice_client import VoiceClient
    except ImportError as e:
        print(f"[ERROR] Cannot import RAGenie modules: {e}")
        print("Make sure you run this from the project root: python voice.py")
        sys.exit(1)

    config = load_config()

    if args.model_size:
        config.voice.stt.model_size = args.model_size
    if args.voice:
        config.voice.tts.voice = args.voice
    if args.wake_word:
        config.voice.wake_word.phrase = args.wake_word
    if args.threshold is not None:
        config.voice.wake_word.threshold = args.threshold
    if args.no_agent:
        config.voice.use_agent = False
    if args.silence_ms is not None:
        config.voice.vad_silence_ms = args.silence_ms

    ws_base = args.ws_url or (
        f"ws://{config.server.host}:{config.server.port}/ws"
    )

    print("=" * 56)
    print("  RAGenie Voice Assistant")
    print("=" * 56)
    print(f"  Wake phrase : {config.voice.wake_word.phrase}")
    print(f"  STT model   : faster-whisper/{config.voice.stt.model_size}")
    print(f"  TTS voice   : {config.voice.tts.voice}")
    _llm_display = (
        config.llm.multi_model["main"].model_name
        if config.llm.multi_model and "main" in config.llm.multi_model
        else config.llm.model_name
    )
    print(f"  LLM model   : {_llm_display}  (via Ollama)")
    print(f"  Agent mode  : {'enabled (RAG + tools)' if config.voice.use_agent else 'disabled (pure LLM)'}")
    print(f"  Server      : {ws_base}")
    print("=" * 56)
    print()
    print("  Make sure RAGenie server is running:  python main.py")
    print()

    client = VoiceClient(config.voice, ws_base)

    async def _run() -> None:
        loop = asyncio.get_running_loop()

        def _sigterm_handler() -> None:
            """Convert SIGTERM into task cancellation so finally blocks run."""
            for task in asyncio.all_tasks(loop):
                task.cancel()

        loop.add_signal_handler(signal.SIGTERM, _sigterm_handler)
        await client.run()

    try:
        asyncio.run(_run())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    main()
