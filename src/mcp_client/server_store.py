"""SQLite-backed persistence for MCP server configurations."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .models import ServerConfig, ServerConfigCreate, ServerConfigPatch
from ..core.logging_config import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_config(row: sqlite3.Row) -> ServerConfig:
    keys = row.keys()
    return ServerConfig(
        id=row["id"],
        name=row["name"],
        transport=row["transport"],
        enabled=bool(row["enabled"]),
        command=row["command"],
        args=json.loads(row["args"]) if row["args"] else None,
        env=json.loads(row["env"]) if row["env"] else None,
        url=row["url"],
        headers=json.loads(row["headers"]) if ("headers" in keys and row["headers"]) else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ServerConfigStore:
    """CRUD store for MCP server configs, backed by SQLite."""

    def __init__(self, db_path: str = "data/mcp_client/servers.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_servers (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL UNIQUE,
                    transport   TEXT NOT NULL CHECK(transport IN ('stdio', 'sse', 'http')),
                    enabled     INTEGER NOT NULL DEFAULT 1,
                    command     TEXT,
                    args        TEXT,
                    env         TEXT,
                    url         TEXT,
                    headers     TEXT,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mcp_servers_name ON mcp_servers(name)"
            )
            # Add headers column to existing DBs that predate this field
            try:
                conn.execute("ALTER TABLE mcp_servers ADD COLUMN headers TEXT")
            except Exception:
                pass
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, data: ServerConfigCreate) -> ServerConfig:
        if self.get_by_name(data.name):
            raise ValueError(f"name already exists: '{data.name}'")
        server_id = str(uuid.uuid4())
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO mcp_servers (id,name,transport,enabled,command,args,env,url,headers,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    server_id, data.name, data.transport, int(data.enabled),
                    data.command,
                    json.dumps(data.args) if data.args is not None else None,
                    json.dumps(data.env) if data.env is not None else None,
                    data.url,
                    json.dumps(data.headers) if data.headers is not None else None,
                    now, now,
                ),
            )
            conn.commit()
        return self.get(server_id)  # type: ignore[return-value]

    def get(self, server_id: str) -> Optional[ServerConfig]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM mcp_servers WHERE id = ?", (server_id,)
            ).fetchone()
        return _row_to_config(row) if row else None

    def get_by_name(self, name: str) -> Optional[ServerConfig]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM mcp_servers WHERE name = ?", (name,)
            ).fetchone()
        return _row_to_config(row) if row else None

    def list(self) -> List[ServerConfig]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM mcp_servers ORDER BY created_at"
            ).fetchall()
        return [_row_to_config(r) for r in rows]

    def update(self, server_id: str, patch: ServerConfigPatch) -> ServerConfig:
        existing = self.get(server_id)
        if existing is None:
            raise KeyError(f"Server not found: {server_id}")

        if patch.name is not None and patch.name != existing.name:
            collision = self.get_by_name(patch.name)
            if collision and collision.id != server_id:
                raise ValueError(f"name already exists: '{patch.name}'")

        fields = []
        params = []
        for attr in ("name", "transport", "command", "url"):
            val = getattr(patch, attr)
            if val is not None:
                fields.append(f"{attr} = ?")
                params.append(val)
        if patch.enabled is not None:
            fields.append("enabled = ?")
            params.append(int(patch.enabled))
        if patch.args is not None:
            fields.append("args = ?")
            params.append(json.dumps(patch.args))
        if patch.env is not None:
            fields.append("env = ?")
            params.append(json.dumps(patch.env))
        if patch.headers is not None:
            fields.append("headers = ?")
            params.append(json.dumps(patch.headers))

        if not fields:
            return existing

        fields.append("updated_at = ?")
        params.append(_now())
        params.append(server_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE mcp_servers SET {', '.join(fields)} WHERE id = ?",
                params,
            )
            conn.commit()
        return self.get(server_id)  # type: ignore[return-value]

    def delete(self, server_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM mcp_servers WHERE id = ?", (server_id,)
            )
            conn.commit()
        return cursor.rowcount > 0

    def migrate_from_yaml(self, mcp_clients: list) -> int:
        """
        Insert entries from config.yaml mcp_clients that do not yet exist in the DB.
        Returns the number of newly inserted rows.
        """
        inserted = 0
        for entry in mcp_clients:
            name = getattr(entry, "name", None) or entry.get("name", "") if isinstance(entry, dict) else entry.name
            if not name:
                continue
            if self.get_by_name(name):
                continue
            try:
                transport = getattr(entry, "transport", None) or (entry.get("transport") if isinstance(entry, dict) else None)
                command = getattr(entry, "command", None) or (entry.get("command") if isinstance(entry, dict) else None)
                args = getattr(entry, "args", None) or (entry.get("args") if isinstance(entry, dict) else None)
                env = getattr(entry, "env", None) or (entry.get("env") if isinstance(entry, dict) else None)
                url = getattr(entry, "url", None) or (entry.get("url") if isinstance(entry, dict) else None)
                enabled = getattr(entry, "enabled", True)
                self.create(ServerConfigCreate(
                    name=name,
                    transport=transport or "stdio",
                    enabled=enabled,
                    command=command,
                    args=args,
                    env=env,
                    url=url,
                ))
                inserted += 1
                logger.info(f"Migrated MCP client '{name}' from config.yaml to DB")
            except Exception as e:
                logger.warning(f"Could not migrate MCP client '{name}': {e}")
        return inserted
