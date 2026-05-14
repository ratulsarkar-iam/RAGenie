import asyncio
import json
import subprocess
from typing import Dict, Any, List, Optional
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class MCPClient:
    """Lightweight MCP client using subprocess stdio transport."""

    def __init__(self, config: dict):
        self.name = config["name"]
        self.command = config.get("command", "python")
        self.args = config.get("args", [])
        self.env = config.get("env")
        self.process: Optional[subprocess.Popen] = None

    async def connect(self) -> None:
        try:
            import os
            env = os.environ.copy()
            if self.env:
                env.update(self.env)

            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            logger.info(f"MCP client '{self.name}' connected")
        except FileNotFoundError:
            logger.warning(f"MCP client '{self.name}' binary not found, using mock mode")
            self.process = None

    async def call(self, action: str, params: dict) -> dict:
        if self.process is None:
            logger.warning(f"MCP client '{self.name}' not running, returning mock response")
            return {"status": "mock", "action": action, "params": params}

        try:
            request = json.dumps({"action": action, "params": params}) + "\n"
            self.process.stdin.write(request.encode())
            self.process.stdin.flush()

            loop = asyncio.get_event_loop()
            response_line = await asyncio.wait_for(
                loop.run_in_executor(None, self.process.stdout.readline),
                timeout=10.0
            )
            return json.loads(response_line.decode().strip())
        except asyncio.TimeoutError:
            logger.error(f"MCP client '{self.name}' timed out")
            return {"status": "error", "message": "Timeout"}
        except Exception as e:
            logger.error(f"MCP client '{self.name}' error: {e}")
            return {"status": "error", "message": str(e)}

    def disconnect(self) -> None:
        if self.process:
            self.process.terminate()
            self.process = None


class MCPManager:
    """Manages MCP client connections and communications."""

    def __init__(self, clients_config: List[dict]):
        self.clients_config = clients_config
        self.clients: Dict[str, MCPClient] = {}

    async def initialize_clients(self) -> None:
        for config in self.clients_config:
            if config.get("enabled", True):
                client = MCPClient(config)
                await client.connect()
                self.clients[config["name"]] = client
        logger.info(f"Initialized {len(self.clients)} MCP clients")

    async def execute_action(self, client_name: str, action: str, params: dict) -> dict:
        client = self.clients.get(client_name)
        if not client:
            raise ValueError(f"MCP client {client_name} not found")
        return await client.call(action, params)

    def shutdown(self) -> None:
        for client in self.clients.values():
            client.disconnect()
