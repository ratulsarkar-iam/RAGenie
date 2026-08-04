#!/bin/bash

# RAGenie Stop Script
# Gracefully shuts down all RAGenie services started by start.sh.
#
# Usage:
#   ./stop.sh

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

PID_FILE="/tmp/.ragenie.pid"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}              RAGenie — Shutting down${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# ── Helper: stop a process by PID ─────────────────────────────────────────────
stop_pid() {
    local label="$1" pid="$2"
    if [ -z "$pid" ]; then return; fi
    if ! kill -0 "$pid" 2>/dev/null; then
        echo -e "  ${label}: already stopped"
        return
    fi
    echo -n "  Stopping ${label} (PID $pid)..."
    kill -TERM "$pid" 2>/dev/null
    # Wait up to 5 s for clean exit
    local i=0
    while kill -0 "$pid" 2>/dev/null && [ $i -lt 5 ]; do
        sleep 1; i=$((i+1))
    done
    # Force-kill if still alive
    if kill -0 "$pid" 2>/dev/null; then
        kill -KILL "$pid" 2>/dev/null
    fi
    echo -e " ${GREEN}done${NC}"
}

# ── Load PIDs from lock file ───────────────────────────────────────────────────
BACKEND_PID=""; FRONTEND_PID=""; VOICE_PID=""; OVERLAY_PID=""

if [ -f "$PID_FILE" ]; then
    # shellcheck disable=SC1090
    source "$PID_FILE"
else
    echo -e "${YELLOW}  No PID file found ($PID_FILE) — falling back to pkill${NC}"
fi

# ── Stop services in reverse startup order ────────────────────────────────────

# Overlay (no user impact, kill first)
if [ -n "$OVERLAY_PID" ]; then
    stop_pid "overlay" "$OVERLAY_PID"
else
    pkill -f "overlay.py" 2>/dev/null && echo -e "  Stopped overlay (pkill)"
fi

# Voice
if [ -n "$VOICE_PID" ]; then
    stop_pid "voice  " "$VOICE_PID"
else
    pkill -f "voice.py" 2>/dev/null && echo -e "  Stopped voice (pkill)"
fi
# Kill any afplay subprocesses orphaned from TTS playback
if pkill -f "afplay" 2>/dev/null; then
    echo -e "  Killed orphaned afplay (TTS audio)"
fi

# Frontend — also kill Vite subprocess
if [ -n "$FRONTEND_PID" ]; then
    pkill -TERM -P "$FRONTEND_PID" 2>/dev/null || true
    stop_pid "frontend" "$FRONTEND_PID"
    pkill -f "vite" 2>/dev/null || true
else
    pkill -f "vite" 2>/dev/null && echo -e "  Stopped frontend (pkill)"
fi

# Backend
if [ -n "$BACKEND_PID" ]; then
    stop_pid "backend " "$BACKEND_PID"
else
    pkill -f "run_server.py" 2>/dev/null && echo -e "  Stopped backend (pkill)"
fi

# ── Cleanup ───────────────────────────────────────────────────────────────────
rm -f "$PID_FILE"
rm -f /tmp/.ragenie_ollama_tags.json
rm -f /tmp/ragenie_cfg_*.py /tmp/ragenie_models_*.py

echo ""
echo -e "${GREEN}✓ All services stopped.${NC}"
