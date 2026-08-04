"""Lightweight IPC bridge between voice_client and the floating overlay.

voice_client calls update_state() on every state transition.
overlay.py polls STATE_FILE every 80 ms and re-renders.

Writes are atomic (write temp + os.replace) so the reader never sees
a partially-written file.
"""
from __future__ import annotations

import json
import os
import time

STATE_FILE = "/tmp/.ragenie_voice_state.json"


def update_state(
    state: str,
    *,
    user_text: str = "",
    agent_text: str = "",
    tool: str = "",
    session: str = "",
) -> None:
    """Atomically write current pipeline state for the overlay to read."""
    try:
        payload = {
            "state": state,
            "user_text": user_text[:120],
            "agent_text": agent_text[:140],
            "tool": tool,
            "session": session,
            "ts": time.time(),
        }
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh)
        os.replace(tmp, STATE_FILE)
    except Exception:
        pass


def clear_state(session: str = "") -> None:
    """Remove the state file — overlay will show DISCONNECTED."""
    update_state("SHUTDOWN", session=session)
    try:
        os.unlink(STATE_FILE)
    except Exception:
        pass
