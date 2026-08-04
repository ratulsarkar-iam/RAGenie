"""Per-user registry of MCPClientManager instances.

Each user gets their own MCPClientManager (own connections, own tool registry),
lazily created on first use and cached for the lifetime of the process. This
guarantees that one user's connected MCP servers/tools are never visible to,
or callable by, another user.
"""
import asyncio
from typing import Callable, Dict, Optional

from .manager import MCPClientManager
from .server_store import ServerConfigStore
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class UserScopedServerStore:
    """Thin adapter that binds a ServerConfigStore to a single user_id.

    Exposes the same call signatures MCPClientManager expects (`list()`,
    `get(id)`), so MCPClientManager itself requires no changes.
    """

    def __init__(self, store: ServerConfigStore, user_id: str):
        self._store = store
        self._user_id = user_id

    def list(self):
        return self._store.list(self._user_id)

    def get(self, server_id: str):
        config = self._store.get(server_id)
        if config is None or config.user_id != self._user_id:
            return None
        return config


class MultiUserMCPManagerRegistry:
    """Owns one MCPClientManager per user_id, created lazily on first access."""

    def __init__(self, store: ServerConfigStore, on_tools_changed: Optional[Callable[[str], None]] = None):
        self._store = store
        self._managers: Dict[str, MCPClientManager] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._on_tools_changed = on_tools_changed  # called with user_id when that user's tools change

    def _lock_for(self, user_id: str) -> asyncio.Lock:
        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()
        return self._locks[user_id]

    async def get_or_create(self, user_id: str) -> MCPClientManager:
        if user_id in self._managers:
            return self._managers[user_id]
        async with self._lock_for(user_id):
            if user_id in self._managers:
                return self._managers[user_id]
            scoped_store = UserScopedServerStore(self._store, user_id)
            mgr = MCPClientManager(scoped_store)  # type: ignore[arg-type]
            if self._on_tools_changed:
                mgr.set_tools_changed_callback(lambda: self._on_tools_changed(user_id))
            try:
                await mgr.initialize_all()
            except Exception as e:
                logger.warning(f"MCP manager init warning for user {user_id}: {e}")
            self._managers[user_id] = mgr
            logger.info(f"Created MCPClientManager for user {user_id}")
            return mgr

    def get_existing(self, user_id: str) -> Optional[MCPClientManager]:
        """Returns the manager only if already created — does not create one."""
        return self._managers.get(user_id)

    async def shutdown_all(self) -> None:
        await asyncio.gather(
            *[mgr.shutdown() for mgr in self._managers.values()],
            return_exceptions=True,
        )
        self._managers.clear()
        logger.info("All per-user MCP client managers shut down")
