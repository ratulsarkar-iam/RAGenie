#!/bin/bash

# RAGenie Startup Script

# Starts backend, frontend, and optionally the voice assistant.
#
# Usage:
#   ./start.sh              — backend + frontend (default)
#   ./start.sh --voice      — also start voice assistant (Hey RAGenie)
#   ./start.sh --no-voice   — suppress voice even if voice.enabled=true in config

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" 
cd "$SCRIPT_DIR"

PID_FILE="/tmp/.ragenie.pid"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

# ── Parse CLI flags ───────────────────────────────────────────────────────────
FLAG_VOICE=""    # --voice forces on; --no-voice forces off; empty = use config
for arg in "$@"; do
    case "$arg" in
        --voice)    FLAG_VOICE="true"  ;;
        --no-voice) FLAG_VOICE="false" ;;
    esac
done

# ── Defaults (overridden by config.yaml) ──────────────────────────────────────
BACKEND_HOST="localhost"
BACKEND_PORT="8000"
FRONTEND_PORT="3000"
MODE="hybrid"
VOICE_ENABLED="false"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}              RAGenie — Starting up${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# ── Load config.yaml (via temp file to avoid heredoc quoting issues) ──────────
if [ -f "config/config.yaml" ] && command -v python3 &>/dev/null; then
    echo -e "${BLUE}▸ Loading config.yaml${NC}"
    _CFG_SCRIPT=$(mktemp /tmp/ragenie_cfg_XXXXXX.py)
    cat > "$_CFG_SCRIPT" << 'PYEOF'
import yaml, re, sys
try:
    cfg = yaml.safe_load(open("config/config.yaml"))
    srv = cfg.get("server", {})
    print('BACKEND_HOST="%s"' % srv.get("host", "localhost"))
    print('BACKEND_PORT=%s' % srv.get("port", 8000))
    for o in srv.get("cors_origins", []):
        m = re.search(r":(\d+)", o)
        if m and m.group(1) in ("3000", "5173"):
            print('FRONTEND_PORT=%s' % m.group(1))
            break
    print('MODE="%s"' % cfg.get("mode", "hybrid"))
    print('VOICE_ENABLED="%s"' % str(cfg.get("voice", {}).get("enabled", False)).lower())
except Exception as e:
    sys.stderr.write("Warning: could not parse config.yaml: %s\n" % e)
PYEOF
    eval "$(python3 "$_CFG_SCRIPT")"
    rm -f "$_CFG_SCRIPT"
fi

# CLI flag overrides config value
[ "$FLAG_VOICE" = "true" ]  && VOICE_ENABLED="true"
[ "$FLAG_VOICE" = "false" ] && VOICE_ENABLED="false"

echo -e "  Mode: ${GREEN}$MODE${NC}  |  Backend: ${GREEN}$BACKEND_HOST:$BACKEND_PORT${NC}  |  Frontend port: ${GREEN}$FRONTEND_PORT${NC}  |  Voice: ${GREEN}$VOICE_ENABLED${NC}"
echo ""

# ── Pre-flight: venv ──────────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}▸ Creating Python virtual environment...${NC}"
    python3 -m venv venv || { echo -e "${RED}✗ Failed to create venv${NC}"; exit 1; }
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate venv
source venv/bin/activate

# ── Install / update Python dependencies ─────────────────────────────────────
echo -e "${YELLOW}▸ Checking Python dependencies (pip install -r requirements.txt)...${NC}"
mkdir -p logs
if pip install -q -r requirements.txt > logs/pip_install.log 2>&1; then
    echo -e "${GREEN}✓ Python dependencies ready${NC}"
else
    echo -e "${YELLOW}  Some packages had issues — see logs/pip_install.log${NC}"
fi

# ── Pre-flight: frontend node_modules ────────────────────────────────────────
if [ "$MODE" != "mcp_server" ]; then
    if [ ! -d "frontend/node_modules" ]; then
        echo -e "${YELLOW}▸ Installing frontend dependencies (first run)...${NC}"
        npm --prefix frontend install 2>&1 | tail -3
        echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
    fi
fi

# ── Pre-flight: portaudio (required by sounddevice / voice assistant) ─────────
if [ "$VOICE_ENABLED" = "true" ]; then
    echo -e "${YELLOW}▸ Checking portaudio (required for voice assistant)...${NC}"
    _PORTAUDIO_OK=false
    if command -v brew &>/dev/null; then
        if brew list portaudio &>/dev/null 2>&1; then
            echo -e "${GREEN}  ✓ portaudio already installed${NC}"
            _PORTAUDIO_OK=true
        else
            echo -e "${YELLOW}  portaudio not found — installing via Homebrew...${NC}"
            if brew install portaudio >> logs/brew_portaudio.log 2>&1; then
                echo -e "${GREEN}  ✓ portaudio installed${NC}"
                _PORTAUDIO_OK=true
            else
                echo -e "${RED}  ✗ brew install portaudio failed — see logs/brew_portaudio.log${NC}"
                echo -e "    Run manually: brew install portaudio"
                echo -e "    Voice assistant will be skipped."
                VOICE_ENABLED="false"
            fi
        fi
    else
        # No brew — check if sounddevice can be imported directly
        if python3 -c "import sounddevice" 2>/dev/null; then
            echo -e "${GREEN}  ✓ sounddevice importable (portaudio present)${NC}"
            _PORTAUDIO_OK=true
        else
            echo -e "${RED}  ✗ portaudio not found and Homebrew not available${NC}"
            echo -e "    Install portaudio for your OS, then: pip install sounddevice"
            echo -e "    Voice assistant will be skipped."
            VOICE_ENABLED="false"
        fi
    fi
fi

# ── Pre-flight: Ollama models ─────────────────────────────────────────────────
# Ollama server itself is managed externally. We just check + pull any missing
# models that RAGenie is configured to use (skipped if Ollama is unreachable).
echo -e "${YELLOW}▸ Checking Ollama models...${NC}"
_OLLAMA_URL="http://localhost:11434"
_MODELS_SCRIPT=$(mktemp /tmp/ragenie_models_XXXXXX.py)
cat > "$_MODELS_SCRIPT" << 'PYEOF'
import yaml, sys
try:
    cfg = yaml.safe_load(open("config/config.yaml"))
    models = set()
    llm = cfg.get("llm", {})
    if llm.get("provider") == "ollama":
        models.add(llm.get("model_name", ""))
    for role in llm.get("multi_model", {}).values():
        if isinstance(role, dict) and role.get("provider") == "ollama":
            models.add(role.get("model_name", ""))
    voice_model = cfg.get("voice", {}).get("llm_model", "")
    if voice_model:
        models.add(voice_model)
    # Filter cloud models and empty strings
    for m in sorted(m for m in models if m and "cloud" not in m.lower()):
        print(m)
except Exception as e:
    sys.stderr.write("Warning: could not read models from config: %s\n" % e)
PYEOF
_REQUIRED_MODELS=$(python3 "$_MODELS_SCRIPT" 2>/dev/null)
rm -f "$_MODELS_SCRIPT"

if curl -sf "${_OLLAMA_URL}/api/tags" > /tmp/.ragenie_ollama_tags.json 2>/dev/null; then
    _AVAILABLE=$(python3 -c "
import json, sys
data=json.load(open('/tmp/.ragenie_ollama_tags.json'))
for m in data.get('models',[]): print(m['name'].split(':')[0]+':'+m['name'].split(':')[1] if ':' in m['name'] else m['name'])
" 2>/dev/null)
    rm -f /tmp/.ragenie_ollama_tags.json
    while IFS= read -r model; do
        [ -z "$model" ] && continue
        _base=$(echo "$model" | cut -d: -f1)
        if echo "$_AVAILABLE" | grep -qE "^${model}$|^${_base}$"; then
            echo -e "  ${GREEN}✓ $model${NC}"
        else
            echo -e "  ${YELLOW}  $model not found — pulling (this may take a while)...${NC}"
            if ollama pull "$model" 2>&1 | tail -3; then
                echo -e "  ${GREEN}  ✓ $model pulled${NC}"
            else
                echo -e "  ${RED}  ✗ Could not pull $model — chat may fail${NC}"
                echo -e "     Run manually: ollama pull $model"
            fi
        fi
    done <<< "$_REQUIRED_MODELS"
else
    echo -e "  ${YELLOW}⚠ Ollama not reachable at ${_OLLAMA_URL} — model check skipped${NC}"
    echo -e "    Ensure Ollama is running before using RAGenie chat."
fi

echo ""

# ── Cleanup on Ctrl+C / SIGTERM ──────────────────────────────────────────────
cleanup() {
    echo ""
    echo -e "${YELLOW}▸ Shutting down...${NC}"
    rm -f "$PID_FILE"

    # Stop frontend first — also kill Vite child spawned by npm
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo -e "  Stopping frontend (PID $FRONTEND_PID)..."
        pkill -TERM -P "$FRONTEND_PID" 2>/dev/null || true   # kill npm's children (Vite)
        kill -TERM "$FRONTEND_PID" 2>/dev/null               # kill npm itself
        wait "$FRONTEND_PID" 2>/dev/null
        pkill -TERM -f "vite" 2>/dev/null || true             # safety net
        echo -e "${GREEN}  ✓ Frontend stopped${NC}"
    fi

    # Stop voice assistant + overlay
    if [ -n "$VOICE_PID" ] && kill -0 "$VOICE_PID" 2>/dev/null; then
        echo -e "  Stopping voice    (PID $VOICE_PID)..."
        kill -TERM "$VOICE_PID" 2>/dev/null
        wait "$VOICE_PID" 2>/dev/null
        echo -e "${GREEN}  ✓ Voice stopped${NC}"
    fi
    if [ -n "$OVERLAY_PID" ] && kill -0 "$OVERLAY_PID" 2>/dev/null; then
        kill -TERM "$OVERLAY_PID" 2>/dev/null
    fi

    # Then stop backend
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "  Stopping backend  (PID $BACKEND_PID)..."
        kill -TERM "$BACKEND_PID" 2>/dev/null
        wait "$BACKEND_PID" 2>/dev/null
        echo -e "${GREEN}  ✓ Backend stopped${NC}"
    fi

    echo -e "${GREEN}Done.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# ── Helper: poll a URL until HTTP 200 is returned ─────────────────────────────
# Usage: wait_for_url <label> <pid> <url> <log_file> [timeout_secs]
wait_for_url() {
    local label="$1" pid="$2" url="$3" log="$4" timeout="${5:-60}"
    local elapsed=0 http_code

    echo -n "   Waiting for $label to be ready "
    while [ "$elapsed" -lt "$timeout" ]; do
        # Bail early if the process already died
        if ! kill -0 "$pid" 2>/dev/null; then
            echo ""
            echo -e "${RED}✗ $label process died. Last lines of $log:${NC}"
            tail -15 "$log" 2>/dev/null
            return 1
        fi

        # Capture HTTP status code; suppress errors so non-zero exit never aborts
        http_code=$(curl -s -o /dev/null -w "%{http_code}" \
            --max-time 3 --connect-timeout 3 \
            "$url" 2>/dev/null) || http_code=""

        if [ "$http_code" = "200" ]; then
            echo -e " ${GREEN}OK (${elapsed}s)${NC}"
            return 0
        fi

        echo -n "."
        sleep 1
        elapsed=$((elapsed + 1))
    done

    echo ""
    echo -e "${RED}✗ $label not ready after ${timeout}s (last HTTP: ${http_code:-no response})${NC}"
    echo -e "${RED}  Check $log for details${NC}"
    tail -15 "$log" 2>/dev/null
    return 1
}

# ── Start backend ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}▸ Starting backend...${NC}"
python run_server.py > logs/server.log 2>&1 &
BACKEND_PID=$!
echo -e "  PID: $BACKEND_PID  |  Log: logs/server.log"

if ! wait_for_url "backend" "$BACKEND_PID" \
        "http://$BACKEND_HOST:$BACKEND_PORT/health" \
        "logs/server.log" 180; then
    kill "$BACKEND_PID" 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✓ Backend  →  http://$BACKEND_HOST:$BACKEND_PORT${NC}"
echo -e "  API Docs:  http://$BACKEND_HOST:$BACKEND_PORT/docs"
if [ "$MODE" = "hybrid" ]; then
    echo -e "  MCP SSE:   http://0.0.0.0:8001/mcp"
fi
echo ""

# ── Start voice assistant (if enabled) ───────────────────────────────────────
VOICE_PID=""
if [ "$VOICE_ENABLED" = "true" ]; then
    echo -e "${YELLOW}▸ Starting voice assistant...${NC}"
    # portaudio already verified in pre-flight — launch directly
    # Launch the floating status overlay (macOS only, requires tkinter)
    OVERLAY_PID=""
    if python3 -c "import tkinter" 2>/dev/null; then
        python src/voice/overlay.py > /dev/null 2>&1 &
        OVERLAY_PID=$!
        echo -e "  Overlay PID: $OVERLAY_PID  (floating status window)"
    fi

    PYTHONUNBUFFERED=1 python voice.py > logs/voice.log 2>&1 &
    VOICE_PID=$!
    echo -e "  PID: $VOICE_PID  |  Log: logs/voice.log"
    # Give it 5 s to boot (model load) then check it's still alive
    sleep 5
    if kill -0 "$VOICE_PID" 2>/dev/null; then
        echo -e "${GREEN}✓ Voice     →  listening for '$(python3 -c "
import yaml; cfg=yaml.safe_load(open('config/config.yaml')); print(cfg.get('voice',{}).get('wake_word',{}).get('phrase','hey_jarvis'))
" 2>/dev/null || echo hey_jarvis)'${NC}"
    else
        echo -e "${RED}  ✗ Voice assistant crashed at startup — see logs/voice.log${NC}"
        tail -10 logs/voice.log 2>/dev/null
        VOICE_PID=""
        [ -n "$OVERLAY_PID" ] && kill "$OVERLAY_PID" 2>/dev/null
    fi
    echo ""
fi

# ── Start frontend ────────────────────────────────────────────────────────────
if [ "$MODE" != "mcp_server" ]; then
    echo -e "${YELLOW}▸ Starting frontend...${NC}"
    npm --prefix frontend run dev > logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo -e "  PID: $FRONTEND_PID  |  Log: logs/frontend.log"

    if ! wait_for_url "frontend" "$FRONTEND_PID" \
            "http://localhost:$FRONTEND_PORT" \
            "logs/frontend.log" 120; then
        kill "$BACKEND_PID" 2>/dev/null
        kill "$FRONTEND_PID" 2>/dev/null
        exit 1
    fi

    echo -e "${GREEN}✓ Frontend →  http://localhost:$FRONTEND_PORT${NC}"
    echo ""
fi

# ── Write PID file (used by stop.sh) ────────────────────────────────────────
{
    echo "BACKEND_PID=$BACKEND_PID"
    [ -n "$FRONTEND_PID" ] && echo "FRONTEND_PID=$FRONTEND_PID"
    [ -n "$VOICE_PID" ]    && echo "VOICE_PID=$VOICE_PID"
    [ -n "$OVERLAY_PID" ]  && echo "OVERLAY_PID=$OVERLAY_PID"
} > "$PID_FILE"

# ── All up ────────────────────────────────────────────────────────────────────
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}         🚀 RAGenie is running!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
[ "$VOICE_ENABLED" = "true" ] && [ -n "$VOICE_PID" ] && \
    echo -e "  🎙  Say the wake phrase to talk to RAGenie"
echo -e "  ${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# ── Keep alive ────────────────────────────────────────────────────────────────
WAIT_PIDS="$BACKEND_PID"
[ "$MODE" != "mcp_server" ] && [ -n "$FRONTEND_PID" ] && WAIT_PIDS="$WAIT_PIDS $FRONTEND_PID"
[ -n "$VOICE_PID" ] && WAIT_PIDS="$WAIT_PIDS $VOICE_PID"
wait $WAIT_PIDS
