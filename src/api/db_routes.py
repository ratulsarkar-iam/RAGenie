"""Developer database browser & SQL execution API.

DEV TOOL — exposes raw SQLite access. Restrict or remove in production.
"""
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["database"])

# Resolve project root two levels up from this file (src/api/db_routes.py → project root)
_PROJECT_ROOT = os.path.realpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)


def _safe_path(db: str) -> str:
    """Resolve db path and ensure it stays inside the project root."""
    if os.path.isabs(db):
        resolved = os.path.realpath(db)
    else:
        resolved = os.path.realpath(os.path.join(_PROJECT_ROOT, db))
    if not resolved.startswith(_PROJECT_ROOT + os.sep) and resolved != _PROJECT_ROOT:
        raise HTTPException(status_code=403, detail="Path is outside the project root")
    return resolved


# ── Discovery ───────────────────────────────────────────────────────────────

@router.get("/api/db/files")
def list_db_files():
    """Return all .db files found under the project data/ directory."""
    result: List[str] = []
    data_dir = os.path.join(_PROJECT_ROOT, "data")
    if os.path.isdir(data_dir):
        for root, _dirs, files in os.walk(data_dir):
            for fname in sorted(files):
                if fname.endswith(".db"):
                    full = os.path.join(root, fname)
                    result.append(os.path.relpath(full, _PROJECT_ROOT))
    return {"files": sorted(result)}


# ── Schema introspection ─────────────────────────────────────────────────────

@router.get("/api/db/tables")
def list_tables(db: str = Query(..., description="Relative path to DB file")):
    """List tables and their row counts for the given DB file."""
    path = _safe_path(db)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"DB file not found: {db}")
    try:
        with sqlite3.connect(path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            result = []
            for (name,) in tables:
                try:
                    cnt = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                except Exception:
                    cnt = -1
                result.append({"name": name, "row_count": cnt})
        return {"tables": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/db/schema")
def table_schema(
    db: str = Query(...),
    table: str = Query(...),
):
    """Return column definitions and index list for the given table."""
    path = _safe_path(db)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"DB file not found: {db}")
    try:
        with sqlite3.connect(path) as conn:
            cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            idxs = conn.execute(f'PRAGMA index_list("{table}")').fetchall()
        return {
            "columns": [
                {
                    "cid": r[0],
                    "name": r[1],
                    "type": r[2] or "ANY",
                    "notnull": bool(r[3]),
                    "default": r[4],
                    "pk": bool(r[5]),
                }
                for r in cols
            ],
            "indexes": [{"name": r[1], "unique": bool(r[2])} for r in idxs],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Query execution ──────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    db: str
    sql: str


@router.post("/api/db/query")
def execute_query(req: QueryRequest):
    """Execute arbitrary SQL and return columns + rows + metadata."""
    path = _safe_path(req.db)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"DB file not found: {req.db}")
    sql = req.sql.strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Empty SQL")

    t0 = time.perf_counter()
    try:
        with sqlite3.connect(path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cur = conn.execute(sql)
            columns: List[str] = [d[0] for d in (cur.description or [])]
            rows: List[List[Any]] = [list(r) for r in cur.fetchall()] if cur.description else []
            affected: int = cur.rowcount if cur.rowcount >= 0 else 0
            conn.commit()
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(f"DB query on '{req.db}': {len(rows)} rows in {duration_ms}ms")
        return {
            "columns": columns,
            "rows": rows,
            "rowcount": len(rows),
            "affected": affected,
            "duration_ms": duration_ms,
        }
    except sqlite3.Error as e:
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
