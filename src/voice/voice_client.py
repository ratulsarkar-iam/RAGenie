import asyncio
import json
import logging
import uuid
from enum import Enum, auto
from typing import TYPE_CHECKING, Dict, Optional

import httpx
import numpy as np

from .audio_io import AudioPlayer, MicCapture
from .command_store import VoiceCommandStore
from .state_bridge import clear_state, update_state
from .stt import STTEngine
from .tts import SentenceChunker, TTSEngine
from .wake_word import WakeWordEngine

if TYPE_CHECKING:
    from ..config.models import VoiceConfig

logger = logging.getLogger("rag_chatbot.voice.voice_client")
# Conversation logger — see voice.py for handler setup (file + stream)
clog = logging.getLogger("voice.conv")


class VoiceState(Enum):
    IDLE = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    WAITING_RESPONSE = auto()
    SPEAKING = auto()


class VoiceClient:
    """End-to-end voice assistant pipeline.

    State machine:
        IDLE → (wake word) → LISTENING → (VAD silence) → TRANSCRIBING
             → WAITING_RESPONSE → SPEAKING → IDLE

    Interrupt: saying the wake phrase again during SPEAKING stops TTS
    and immediately starts listening for a new query.

    Connects to the existing RAGenie WebSocket endpoint:
        ws://<host>:<port>/ws/<client_id>
    """

    def __init__(self, config: "VoiceConfig", ws_url: str):
        self._cfg = config
        self._ws_url = ws_url
        self._http_base = self._http_base_from_ws(ws_url)
        self._active_session: Optional[Dict[str, str]] = None  # set at wake-word time
        self._state = VoiceState.IDLE
        self._session_id = uuid.uuid4().hex[:8]
        self._running = False

        self._mic = MicCapture()
        self._player = AudioPlayer()
        self._wake = WakeWordEngine(
            phrase=config.wake_word.phrase,
            model_path=config.wake_word.model_path,
            threshold=config.wake_word.threshold,
        )
        self._stt = STTEngine(config.stt)
        self._tts = TTSEngine(config.tts)
        self._commands = VoiceCommandStore(config.command_history_db, config.command_history_days)

    @staticmethod
    def _http_base_from_ws(ws_url: str) -> str:
        """Derive the REST base URL from the WS base URL,
        e.g. 'ws://localhost:8000/ws' -> 'http://localhost:8000'."""
        base = ws_url.replace("wss://", "https://").replace("ws://", "http://")
        if base.endswith("/ws"):
            base = base[: -len("/ws")]
        return base

    async def _get_active_session(self) -> Optional[Dict[str, str]]:
        """Ask the backend who is currently logged into the web UI.

        The voice assistant acts as *that* user's personal assistant — it has
        no account of its own. Returns None (and logs a clear message) if
        nobody is logged in or the backend is unreachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._http_base}/api/auth/voice-session")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()  # {user_id, email, access_token}
        except Exception as e:
            logger.warning(f"Could not check active session: {e}")
            return None

    async def _speak(self, text: str) -> None:
        """Speak a one-off message outside the normal streaming pipeline
        (e.g. 'please log in')."""
        chunker = SentenceChunker()
        queue: asyncio.Queue = asyncio.Queue()
        speak_task = asyncio.create_task(self._tts.speak_stream(chunker, self._player, queue))
        await queue.put(("stream_token", text))
        await queue.put(None)
        await speak_task

    # ── Public ────────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Main loop. Runs until KeyboardInterrupt or task cancellation."""
        self._mic.start()
        self._running = True
        logger.info(f"VoiceClient started (session={self._session_id})")
        clog.info(f"{'='*56}")
        clog.info(f"  SESSION START  [{self._session_id}]")
        clog.info(f"  Wake phrase : {self._cfg.wake_word.phrase}")
        clog.info(f"{'='*56}")
        clog.info(f"🎙  Waiting for wake phrase '{self._cfg.wake_word.phrase}'...")
        update_state("IDLE", session=self._session_id)

        try:
            while self._running:
                try:
                    await self._step()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Pipeline error: {e}", exc_info=True)
                    self._state = VoiceState.IDLE
                    clog.info(f"⚠  ERROR: {e} — returning to idle.")
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            await self._shutdown()

    # ── State machine ─────────────────────────────────────────────────────────

    async def _step(self) -> None:
        if self._state == VoiceState.IDLE:
            loop = asyncio.get_running_loop()
            chunk = await loop.run_in_executor(
                None, self._mic.read_chunk, WakeWordEngine.CHUNK_SAMPLES
            )
            if self._wake.process_chunk(chunk):
                self._wake.reset()
                clog.info(f"🔔 WAKE WORD detected")

                session = await self._get_active_session()
                if session is None:
                    clog.info("   🔒 No user is logged in — asking to log in.")
                    logger.info("Voice command refused: no active web session")
                    update_state("IDLE", session=self._session_id)
                    await self._speak("Please log in to RAGenie before using voice commands.")
                    return
                self._active_session = session

                self._state = VoiceState.LISTENING
                clog.info(f"   — listening (as {session['email']})")
                update_state("LISTENING", session=self._session_id)
                await self._speak_ready()
                self._mic.flush()  # discard audio captured during chime
                clog.info("🔊 Speak now...")

        elif self._state == VoiceState.LISTENING:
            clog.info("   ⏺  Recording...")
            loop = asyncio.get_running_loop()
            audio = await loop.run_in_executor(
                None,
                self._stt.collect_utterance,
                self._mic,
                self._cfg.vad_silence_ms,
            )

            self._state = VoiceState.TRANSCRIBING
            clog.info("   🔄 Transcribing...")
            update_state("TRANSCRIBING", session=self._session_id)
            text = await loop.run_in_executor(None, self._stt.transcribe, audio)
            text = text.strip()

            if not text:
                clog.info(f"⚠  Nothing detected. Returning to idle.")
                self._state = VoiceState.IDLE
                return

            clog.info(f"")
            clog.info(f"� USER: {text}")
            self._state = VoiceState.WAITING_RESPONSE
            update_state("WAITING_RESPONSE", user_text=text, session=self._session_id)
            try:
                await self._handle_response(text)
            except Exception as e:
                logger.error(f"Response error: {e}", exc_info=True)
            finally:
                self._state = VoiceState.IDLE
                update_state("IDLE", session=self._session_id)
                clog.info(f"")
                clog.info(f"{'─'*56}")
                clog.info(f"🎙  Waiting for wake phrase '{self._cfg.wake_word.phrase}'...")

    # ── Audio notification ────────────────────────────────────────────────────

    async def _speak_ready(self) -> None:
        """Play a short 660 Hz chime to signal 'ready to listen'.

        Using a tone instead of TTS (say "Listening") avoids the echo problem:
        speech played through speakers gets picked up by the mic, triggers
        Silero VAD, and pollutes the STT recording with garbage audio.
        A pure tone is not detected as speech by the VAD model.
        """
        loop = asyncio.get_running_loop()

        def _chime():
            try:
                import numpy as np
                import sounddevice as sd
                sr = 16000
                t = np.linspace(0, 0.12, int(sr * 0.12), dtype=np.float32)
                tone = (0.25 * np.sin(2 * np.pi * 660 * t)).astype(np.float32)
                sd.play(tone, samplerate=sr, blocking=True)
                sd.wait()
            except Exception:
                pass

        await loop.run_in_executor(None, _chime)
        # Brief pause for the chime to fade before mic capture starts
        await asyncio.sleep(0.3)

    # ── Wake-word interrupt task ──────────────────────────────────────────────

    async def _watch_for_wake_interrupt(
        self,
        interrupt_event: asyncio.Event,
        stop_event: asyncio.Event,
    ) -> None:
        """Background task running during agent response.

        Uses a *lower* threshold (INTERRUPT_THRESHOLD) because TTS audio
        leaking from the speaker raises the noise floor, making the normal
        threshold (0.50) too conservative.  Only started after the first
        stream_token so it never fires during silent tool-call waiting.

        *interrupt_event* — set ONLY when the user genuinely interrupts.
        *stop_event*      — set when the response finishes naturally; used
                            to exit this loop without marking an interrupt.
        """
        INTERRUPT_THRESHOLD = 0.20   # lower than idle threshold; TTS noise raises floor
        loop = asyncio.get_running_loop()

        # Let the first TTS sentence start before enabling interrupt
        await asyncio.sleep(1.0)
        self._wake.reset()

        while not stop_event.is_set():
            try:
                chunk = await loop.run_in_executor(
                    None, self._mic.read_chunk, WakeWordEngine.CHUNK_SAMPLES
                )

                # ── RMS barge-in: any voice above threshold interrupts immediately ──
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                rms_fired  = self._player.is_playing() and rms >= self._cfg.barge_in_threshold
                wake_fired = self._wake.process_chunk(chunk, threshold=INTERRUPT_THRESHOLD)

                if rms_fired or wake_fired:
                    reason = "wake phrase" if wake_fired else f"voice barge-in (rms={rms:.4f})"
                    clog.info(f"⚡ INTERRUPT — {reason} detected")
                    logger.info(f"Interrupt triggered by {reason}")
                    update_state("INTERRUPTED", session=self._session_id)
                    interrupt_event.set()
                    stop_event.set()
                    self._player.stop()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Wake interrupt task: {e}")

    # ── Response handling ─────────────────────────────────────────────────────

    async def _handle_response(self, text: str, depth: int = 0) -> None:
        """Open WebSocket to RAGenie, stream tokens → TTS sentence-by-sentence.

        A background _watch_for_wake_interrupt task runs concurrently.
        If the user says the wake phrase during the response:
          1. TTS playback stops immediately.
          2. 'Listening' is spoken.
          3. The new query is captured and routed back here (depth + 1).
        """
        if depth > 3:
            logger.warning("Max interrupt depth reached.")
            return

        try:
            import websockets
        except ImportError:
            raise RuntimeError("websockets is not installed. Run: pip install websockets")

        conversation_id = f"{self._cfg.conversation_id_prefix}-{self._session_id}"
        client_id = f"voice-{self._session_id}"

        def _build_url(token: Optional[str]) -> str:
            base = f"{self._ws_url}/{client_id}"
            return f"{base}?token={token}" if token else base

        message = {
            "message": text,
            "conversation_id": conversation_id,
            "use_agent": self._cfg.use_agent,
            "use_reasoning": False,
            "model": self._cfg.llm_model,
        }

        chunker = SentenceChunker()
        token_queue: asyncio.Queue = asyncio.Queue()
        interrupt_event = asyncio.Event()  # set ONLY when wake phrase detected
        stop_event      = asyncio.Event()  # set to exit wake_task on natural completion
        wake_task = None  # created only after first stream_token
        response_tokens: list = []  # accumulate full agent response

        speak_task = asyncio.create_task(
            self._tts.speak_stream(chunker, self._player, token_queue)
        )

        # ── Connect with retry (handles backend-down / ECONNREFUSED / auth) ───
        MAX_RETRIES = 3
        RETRY_DELAY = 4.0
        connected = False
        auth_failed = False
        for attempt in range(1, MAX_RETRIES + 1):
            session = self._active_session if attempt == 1 else await self._get_active_session()
            if session is None:
                # Nobody is logged in (any more) — no point retrying.
                auth_failed = True
                break
            self._active_session = session
            url = _build_url(session["access_token"])
            try:
                ws_conn = await websockets.connect(url)
                connected = True
                break
            except websockets.exceptions.InvalidStatusCode as conn_err:
                # Auth rejection (401/403/4401) — the token was stale. Force a
                # fresh session lookup on the next attempt rather than retrying
                # the exact same (failing) request.
                self._active_session = None
                if conn_err.status_code in (401, 403):
                    auth_failed = True
                logger.warning(f"WS connect attempt {attempt} rejected (HTTP {conn_err.status_code}): {conn_err}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(1.0)
            except (OSError, websockets.exceptions.WebSocketException) as conn_err:
                if attempt == 1:
                    clog.info("   ⚠  Backend not reachable — retrying…")
                    logger.warning(f"WS connect attempt {attempt} failed: {conn_err}")
                    update_state("WAITING_RESPONSE",
                                 user_text=text, tool="⚠ reconnecting…",
                                 session=self._session_id)
                    # Speak a friendly warning via TTS
                    await token_queue.put(("stream_token",
                        "Sorry, the backend is not reachable right now. "
                        "I'll retry in a moment."))
                    await token_queue.put(None)
                    await speak_task
                    speak_task = asyncio.create_task(
                        self._tts.speak_stream(
                            SentenceChunker(), self._player, token_queue := asyncio.Queue())
                    )
                else:
                    logger.warning(f"WS connect attempt {attempt} failed: {conn_err}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)

        if not connected:
            if auth_failed:
                clog.info("   🔒 No user logged in — asking to log in.")
                logger.info("Voice command aborted: no active web session")
                await token_queue.put(("stream_token",
                    "Please log in to RAGenie before using voice commands."))
            else:
                clog.info("   ✗ Backend unreachable — returning to idle.")
                logger.error(f"WebSocket: backend unreachable after {MAX_RETRIES} attempts")
                await token_queue.put(("stream_token",
                    "The backend server is still offline. Please start RAGenie and try again."))
            await token_queue.put(None)
            await speak_task
            return

        try:
            ws = ws_conn   # already connected — no async-with needed
            await ws.send(json.dumps(message))
            logger.info(f"Sent to RAGenie: {text[:60]}")
            clog.info("   ⏳ Waiting for RAGenie response...")
            if True:       # indent block kept for minimal diff

                while True:
                    if interrupt_event.is_set():
                        await token_queue.put(None)
                        break

                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.3)
                    except asyncio.TimeoutError:
                        continue

                    event = json.loads(raw)
                    etype = event.get("type", "")

                    if etype == "user_message":
                        continue

                    elif etype == "tool_call":
                        tool_name = event.get("tool", "")
                        if tool_name and not tool_name.startswith("_"):
                            clog.info(f"   🔧 TOOL: {tool_name}")
                            update_state("WAITING_RESPONSE",
                                         user_text=text, tool=tool_name,
                                         session=self._session_id)

                    elif etype == "stream_token":
                        self._state = VoiceState.SPEAKING
                        token = event["content"]
                        response_tokens.append(token)
                        if wake_task is None:
                            # TTS is now playing — safe to start interrupt monitoring
                            clog.info("   🔊 Speaking response...")
                            update_state("SPEAKING", user_text=text,
                                         agent_text="".join(response_tokens),
                                         session=self._session_id)
                            wake_task = asyncio.create_task(
                                self._watch_for_wake_interrupt(
                                    interrupt_event, stop_event)
                            )
                        await token_queue.put(("stream_token", token))

                    elif etype == "assistant_message":
                        self._state = VoiceState.SPEAKING
                        content = event.get("content", "")
                        response_tokens.append(content)
                        await token_queue.put(("assistant_message", content))
                        break

                    elif etype == "stream_end":
                        await token_queue.put(None)
                        break

                    elif etype == "error":
                        err = event.get('content', 'unknown error')
                        logger.error(f"RAGenie error: {err}")
                        clog.info(f"   ❌ RAGenie error: {err}")
                        await token_queue.put(None)
                        break

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await token_queue.put(None)
        finally:
            try:
                await ws_conn.close()
            except Exception:
                pass
            stop_event.set()        # exit wake_task loop (natural completion)
            if wake_task is not None:
                wake_task.cancel()
                try:
                    await wake_task
                except asyncio.CancelledError:
                    pass

        await speak_task

        # Log the full agent response once TTS is done
        full_response = ""
        if response_tokens:
            full_response = "".join(response_tokens).strip()
            if full_response:
                clog.info(f"🤖 AGENT: {full_response}")
                update_state("SPEAKING", user_text=text,
                             agent_text=full_response,
                             session=self._session_id)

        if self._active_session:
            self._commands.add(self._active_session["user_id"], text, full_response)

        if interrupt_event.is_set() and depth < 3:
            # Stop player, flush mic buffer to discard TTS echo, drain speaker hardware
            self._player.stop()
            self._mic.flush()
            await asyncio.sleep(0.8)   # let OS audio buffer drain fully
            self._mic.flush()          # flush again after drain
            self._wake.reset()
            await self._speak_ready()  # 660 Hz chime + 0.3s
            self._mic.flush()          # final flush after chime
            self._state = VoiceState.LISTENING
            update_state("LISTENING", session=self._session_id)
            loop = asyncio.get_running_loop()
            clog.info("   ⏺  Recording (after interrupt)...")
            audio = await loop.run_in_executor(
                None, self._stt.collect_utterance, self._mic, self._cfg.vad_silence_ms
            )
            clog.info("   🔄 Transcribing...")
            update_state("TRANSCRIBING", session=self._session_id)
            new_text = await loop.run_in_executor(None, self._stt.transcribe, audio)
            new_text = new_text.strip()
            if new_text:
                clog.info(f"")
                update_state("WAITING_RESPONSE", user_text=new_text, session=self._session_id)
                await self._handle_response(new_text, depth=depth + 1)

    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def _shutdown(self) -> None:
        self._running = False
        self._player.stop()
        self._mic.stop()
        self._wake.close()
        clog.info(f"{'='*56}")
        clog.info(f"  SESSION END  [{self._session_id}]")
        clog.info(f"{'='*56}")
        logger.info("VoiceClient shutdown complete")
        clear_state(session=self._session_id)
