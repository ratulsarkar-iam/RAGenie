#!/usr/bin/env python3
"""Startup script for the RAG Chatbot API server."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.api.app import run_server
from src.config.loader import load_config


def main():
    # Load configuration
    config = load_config()
    
    print("="*60)
    print("RAG CHATBOT API SERVER")
    print("="*60)
    print(f"Starting server on {config.server.host}:{config.server.port}")
    print(f"API docs: http://{config.server.host}:{config.server.port}/docs")
    print("="*60)
    print()
    
    # Run server
    run_server(host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
