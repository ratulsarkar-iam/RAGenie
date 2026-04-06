#!/usr/bin/env python3
"""
Test script to demonstrate multi-model usage
"""

import asyncio
import websockets
import json

async def test_models():
    uri = "ws://localhost:8000/ws/test_client"
    
    async with websockets.connect(uri) as websocket:
        # Test 1: Reasoning model (deepseek-r1:1.5b)
        print("\n=== Testing REASONING model (deepseek-r1:1.5b) ===")
        message1 = {
            "message": "Solve this step by step: If a train travels 300 km in 3 hours, what is its speed?",
            "conversation_id": "test",
            "use_agent": False,
            "use_reasoning": True
        }
        await websocket.send(json.dumps(message1))
        
        # Collect response
        response_parts = []
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            if data.get("type") == "stream_end":
                break
            elif data.get("type") == "stream_token":
                response_parts.append(data.get("content", ""))
        
        print(f"Response: {''.join(response_parts)[:100]}...")
        
        # Test 2: Main model (qwen2.5:7b)
        print("\n=== Testing MAIN model (qwen2.5:7b) ===")
        message2 = {
            "message": "What are the primary colors?",
            "conversation_id": "test",
            "use_agent": False,
            "use_reasoning": False
        }
        await websocket.send(json.dumps(message2))
        
        # Collect response
        response_parts = []
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            if data.get("type") == "stream_end":
                break
            elif data.get("type") == "stream_token":
                response_parts.append(data.get("content", ""))
        
        print(f"Response: {''.join(response_parts)[:100]}...")
        
        # Test 3: Fallback model (llama3.2) - This is used when main model fails
        print("\n=== Testing FALLBACK model (llama3.2) ===")
        print("Note: Fallback is used automatically when main model fails")
        message3 = {
            "message": "Tell me a short joke",
            "conversation_id": "test",
            "use_agent": False,
            "use_reasoning": False
        }
        await websocket.send(json.dumps(message3))
        
        # Collect response
        response_parts = []
        while True:
            response = await websocket.recv()
            data = json.loads(response)
            if data.get("type") == "stream_end":
                break
            elif data.get("type") == "stream_token":
                response_parts.append(data.get("content", ""))
        
        print(f"Response: {''.join(response_parts)[:100]}...")

if __name__ == "__main__":
    print("Testing multi-model setup...")
    print("Make sure the server is running with: python src/api/app.py")
    print("Watch the logs to see which model is being used for each request.")
    asyncio.run(test_models())
