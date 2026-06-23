#!/bin/bash

# RAGenie Startup Script
<<<<<<< HEAD
# Starts backend (and optionally frontend) based on config.yaml.
=======
# This script activates the virtual environment and starts both backend and frontend
# Supports multiple operational modes based on config.yaml.
>>>>>>> 9f5e817fa338fd28ac223784e95a9ce60c26af52

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" 
cd "$SCRIPT_DIR"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

# ── Defaults (overridden by config.yaml) ──────────────────────────────────────
BACKEND_HOST="localhost"
BACKEND_PORT="8000"
FRONTEND_PORT="3000"
MODE="hybrid"

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
except Exception as e:
    sys.stderr.write("Warning: could not parse config.yaml: %s\n" % e)
PYEOF
    eval "$(python3 "$_CFG_SCRIPT")"
    rm -f "$_CFG_SCRIPT"
fi

echo -e "  Mode: ${GREEN}$MODE${NC}  |  Backend: ${GREEN}$BACKEND_HOST:$BACKEND_PORT${NC}  |  Frontend port: ${GREEN}$FRONTEND_PORT${NC}"
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

echo ""

# ── Cleanup on Ctrl+C / SIGTERM ──────────────────────────────────────────────
cleanup() {
    echo ""
    echo -e "${YELLOW}▸ Shutting down...${NC}"

    # Stop frontend first — also kill Vite child spawned by npm
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo -e "  Stopping frontend (PID $FRONTEND_PID)..."
        pkill -TERM -P "$FRONTEND_PID" 2>/dev/null || true   # kill npm's children (Vite)
        kill -TERM "$FRONTEND_PID" 2>/dev/null               # kill npm itself
        wait "$FRONTEND_PID" 2>/dev/null
        pkill -TERM -f "vite" 2>/dev/null || true             # safety net
        echo -e "${GREEN}  ✓ Frontend stopped${NC}"
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

# ── All up ────────────────────────────────────────────────────────────────────
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}         🚀 RAGenie is running!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# ── Keep alive ────────────────────────────────────────────────────────────────
if [ "$MODE" != "mcp_server" ] && [ -n "$FRONTEND_PID" ]; then
    wait "$BACKEND_PID" "$FRONTEND_PID"
else
    wait "$BACKEND_PID"
fi
