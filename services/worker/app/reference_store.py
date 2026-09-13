from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from .job_store import DB_PATH
from .supabase_rest import configured as supabase_configured
from .supabase_rest import delete as supabase_delete
from .supabase_rest import select as supabase_select
from .supabase_rest import upsert as supabase_upsert

_LOCK = Lock()


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def init_reference_store() -> None:
    if supabase_configured():
        return
    with _LOCK, _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reference_assets (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def save_reference(reference_id: str, path: str, payload: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    if supabase_configured():
        supabase_upsert(
            "content_studio_references",
            {
                "id": reference_id,
                "name": str(payload.get("name") or reference_id),
                "kind": str(payload.get("kind") or "image"),
                "mime_type": str(payload.get("mime_type") or "application/octet-stream"),
                "size_bytes": int(payload.get("size_bytes") or 0),
                "sha256": str(payload.get("sha256") or reference_id),
                "storage_path": path,
                "analysis_status": str(payload.get("analysis_status") or "queued"),
                "analysis": payload.get("analysis"),
                "analysis_error": payload.get("analysis_error"),
                "updated_at": now,
            },
            on_conflict="id",
        )
        return

    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with _LOCK, _connect() as connection:
        existing = connection.execute("SELECT created_at FROM reference_assets WHERE id = ?", (reference_id,)).fetchone()
        created_at = existing["created_at"] if existing else now
        connection.execute(
            """
            INSERT INTO reference_assets (id, path, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET path = excluded.path, payload_json = excluded.payload_json, updated_at = excluded.updated_at
            """,
            (reference_id, path, data, created_at, now),
        )


def load_references() -> list[dict[str, Any]]:
    if supabase_configured():
        rows = supabase_select("content_studio_references", order="updated_at.desc")
        results: list[dict[str, Any]] = []
        for row in rows:
            payload = {
                "id": row.get("id"),
                "name": row.get("name"),
                "kind": row.get("kind"),
                "mime_type": row.get("mime_type"),
                "size_bytes": row.get("size_bytes"),
                "sha256": row.get("sha256"),
                "analysis_status": row.get("analysis_status"),
                "analysis": row.get("analysis"),
                "analysis_error": row.get("analysis_error"),
            }
            results.append({"id": row.get("id"), "path": row.get("storage_path") or "", "payload": payload})
        return results

    init_reference_store()
    with _LOCK, _connect() as connection:
        rows = connection.execute("SELECT id, path, payload_json FROM reference_assets ORDER BY updated_at DESC").fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            results.append({"id": row["id"], "path": row["path"], "payload": payload})
    return results


def delete_reference(reference_id: str) -> None:
    if supabase_configured():
        supabase_delete("content_studio_references", {"id": f"eq.{reference_id}"})
        return
    with _LOCK, _connect() as connection:
        connection.execute("DELETE FROM reference_assets WHERE id = ?", (reference_id,))
