#!/bin/bash

# RAGenie Startup Script
# This script activates the virtual environment and starts both backend and frontend
# Supports multiple operational modes based on config.yaml.

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Default values (can be overridden by config)
BACKEND_HOST="localhost"
BACKEND_PORT="8000"
FRONTEND_PORT="3000"
MODE="hybrid"

# Function to load configuration from config.yaml
load_config() {
    if [ -f "config/config.yaml" ]; then
        echo -e "${GREEN}✓ Loading configuration from config.yaml${NC}"
        
        # Extract values from YAML using basic parsing
        if command -v python3 >/dev/null 2>&1; then
            eval $(python3 -c "
import yaml, sys, re
try:
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Server config
    if 'server' in config:
        print(f'BACKEND_HOST=\"{config[\"server\"].get(\"host\", \"localhost\")}\"')
        print(f'BACKEND_PORT={config[\"server\"].get(\"port\", 8000)}')
        if 'cors_origins' in config['server']:
            for origin in config['server']['cors_origins']:
                if '3000' in origin or '5173' in origin:
                    port = re.search(r':(\d+)', origin)
                    if port:
                        print(f'FRONTEND_PORT={port.group(1)}')
                    break
    
    # Mode
    print(f'MODE=\"{config.get(\"mode\", \"hybrid\")}\"')
    
except Exception as e:
    print(f'echo Warning: Could not parse config.yaml: {e}', file=sys.stderr)
")
        else
            echo -e "${YELLOW}Warning: Python3 not found, using default configuration${NC}"
        fi
    else
        echo -e "${YELLOW}Warning: config/config.yaml not found, using default configuration${NC}"
    fi
}

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}       RAGenie - Starting Backend & Frontend${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Load configuration
load_config

echo -e "${BLUE}Configuration:${NC}"
echo -e "  Mode: ${GREEN}$MODE${NC}"
echo -e "  Backend: ${GREEN}$BACKEND_HOST:$BACKEND_PORT${NC}"
echo -e "  Frontend: ${GREEN}localhost:$FRONTEND_PORT${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}Error: Virtual environment not found!${NC}"
    echo -e "${YELLOW}Please run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt${NC}"
    exit 1
fi

# Check if frontend node_modules exists
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Frontend dependencies not installed. Installing...${NC}"
    cd frontend
    npm install
    cd ..
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
    echo ""
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down servers...${NC}"
    
    # Send SIGTERM to frontend first (it usually shuts down faster)
    if [ ! -z "$FRONTEND_PID" ] && kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${YELLOW}⏳ Stopping frontend...${NC}"
        kill $FRONTEND_PID 2>/dev/null
        
        # Wait for frontend to stop (max 30 seconds)
        COUNTER=0
        while kill -0 $FRONTEND_PID 2>/dev/null && [ $COUNTER -lt 30 ]; do
            sleep 1
            COUNTER=$((COUNTER + 1))
        done
        
        # Force kill if still running
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            echo -e "${YELLOW}   Force stopping frontend...${NC}"
            kill -9 $FRONTEND_PID 2>/dev/null
        fi
        echo -e "${GREEN}✓ Frontend stopped${NC}"
    fi
    
    # Send SIGTERM to backend
    if [ ! -z "$BACKEND_PID" ] && kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${YELLOW}⏳ Stopping backend...${NC}"
        kill $BACKEND_PID 2>/dev/null
        
        # Wait for backend to stop (max 30 seconds)
        COUNTER=0
        while kill -0 $BACKEND_PID 2>/dev/null && [ $COUNTER -lt 30 ]; do
            sleep 1
            COUNTER=$((COUNTER + 1))
        done
        
        # Force kill if still running
        if kill -0 $BACKEND_PID 2>/dev/null; then
            echo -e "${YELLOW}   Force stopping backend...${NC}"
            kill -9 $BACKEND_PID 2>/dev/null
        fi
        echo -e "${GREEN}✓ Backend stopped${NC}"
    fi
    
    # Kill any remaining child processes
    pkill -P $$ 2>/dev/null
    
    echo -e "${GREEN}Shutdown complete${NC}"
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT SIGTERM

# Activate virtual environment
echo -e "${GREEN}✓ Activating virtual environment...${NC}"
source venv/bin/activate

# Install/update Python dependencies if needed
echo -e "${YELLOW}⏳ Checking Python dependencies...${NC}"
pip install -r requirements.txt > logs/pip_install.log 2>&1 || {
    echo -e "${YELLOW}Some dependencies may have failed to install. Check logs/pip_install.log${NC}"
}
echo -e "${GREEN}✓ Dependencies ready${NC}"

# Start backend server in background
echo -e "${YELLOW}⏳ Starting backend server...${NC}"
python run_server.py > logs/server.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to be ready with progress indicator
echo -n "   Waiting for backend to be ready "
MAX_WAIT=180  # Maximum wait time in seconds (3 minutes)
COUNTER=0
BACKEND_READY=false

while [ $COUNTER -lt $MAX_WAIT ]; do
    # Check if process is still running
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo ""
        echo -e "${RED}✗ Backend process died. Check logs/server.log${NC}"
        echo -e "${RED}Last 10 lines of server log:${NC}"
        tail -10 logs/server.log 2>/dev/null || echo "No log file found"
        exit 1
    fi
    
    # Check if backend is responding
    if curl -s "http://$BACKEND_HOST:$BACKEND_PORT/health" > /dev/null 2>&1; then
        BACKEND_READY=true
        break
    fi
    
    # Show progress
    echo -n "."
    sleep 1
    COUNTER=$((COUNTER + 1))
done

echo ""

if [ "$BACKEND_READY" = false ]; then
    echo -e "${RED}✗ Backend failed to start within ${MAX_WAIT}s. Check logs/server.log${NC}"
    echo -e "${RED}Last 10 lines of server log:${NC}"
    tail -10 logs/server.log 2>/dev/null || echo "No log file found"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✓ Backend ready on http://$BACKEND_HOST:$BACKEND_PORT${NC}"

# Start frontend in background (only if mode is not "mcp_server")
if [ "$MODE" != "mcp_server" ]; then
    echo -e "${YELLOW}⏳ Starting frontend...${NC}"
    cd frontend
    npm run dev > ../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    cd ..
    
    # Wait for frontend to be ready with progress indicator
    echo -n "   Waiting for frontend to be ready "
    MAX_WAIT_FRONTEND=180  # Maximum wait time in seconds (3 minutes)
    COUNTER=0
    FRONTEND_READY=false
    
    while [ $COUNTER -lt $MAX_WAIT_FRONTEND ]; do
        # Check if process is still running
        if ! kill -0 $FRONTEND_PID 2>/dev/null; then
            echo ""
            echo -e "${RED}✗ Frontend process died. Check logs/frontend.log${NC}"
            echo -e "${RED}Last 10 lines of frontend log:${NC}"
            tail -10 logs/frontend.log 2>/dev/null || echo "No log file found"
            kill $BACKEND_PID 2>/dev/null
            exit 1
        fi
        
        # Check if frontend is responding (Vite dev server)
        if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
            FRONTEND_READY=true
            break
        fi
        
        # Show progress
        echo -n "."
        sleep 1
        COUNTER=$((COUNTER + 1))
    done
    
    echo ""
    
    if [ "$FRONTEND_READY" = false ]; then
        echo -e "${RED}✗ Frontend failed to start within ${MAX_WAIT_FRONTEND}s. Check logs/frontend.log${NC}"
        echo -e "${RED}Last 10 lines of frontend log:${NC}"
        tail -10 logs/frontend.log 2>/dev/null || echo "No log file found"
        kill $BACKEND_PID 2>/dev/null
        kill $FRONTEND_PID 2>/dev/null
        exit 1
    fi
    
    echo -e "${GREEN}✓ Frontend ready on http://localhost:$FRONTEND_PORT${NC}"
else
    echo -e "${YELLOW}Frontend skipped (mode: $MODE)${NC}"
fi

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}       🎉 RAGenie is running!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""

if [ "$MODE" != "mcp_server" ]; then
    echo -e "  ${BLUE}Frontend:${NC}  http://localhost:$FRONTEND_PORT"
fi
echo -e "  ${BLUE}Backend:${NC}   http://$BACKEND_HOST:$BACKEND_PORT"
echo -e "  ${BLUE}API Docs:${NC}  http://$BACKEND_HOST:$BACKEND_PORT/docs"
echo ""

if [ "$MODE" = "hybrid" ]; then
    echo -e "  ${BLUE}MCP Server:${NC} SSE transport available"
fi

echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""
echo -e "${BLUE}Logs:${NC}"
echo -e "  Backend:  logs/server.log"
if [ "$MODE" != "mcp_server" ]; then
    echo -e "  Frontend: logs/frontend.log"
fi
echo -e "  Dependencies: logs/pip_install.log"
echo ""

# Function to show live logs on demand
show_logs() {
    echo -e "${BLUE}Recent backend logs:${NC}"
    tail -5 logs/server.log 2>/dev/null || echo "No backend logs available"
    echo ""
    if [ "$MODE" != "mcp_server" ]; then
        echo -e "${BLUE}Recent frontend logs:${NC}"
        tail -5 logs/frontend.log 2>/dev/null || echo "No frontend logs available"
    fi
}

# Wait for both processes (or just backend if frontend is not running)
if [ "$MODE" != "mcp_server" ] && [ ! -z "$FRONTEND_PID" ]; then
    wait $BACKEND_PID $FRONTEND_PID
else
    wait $BACKEND_PID
fi
