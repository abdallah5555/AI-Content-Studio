from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

DB_PATH = Path(os.getenv("JOB_DB_PATH", "data/ai_content_studio.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_LOCK = Lock()


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def init_job_store() -> None:
    with _LOCK, _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                title TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_updated_at ON jobs(updated_at DESC)")


def save_job(job: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    created_at = str(job.get("created_at") or now)
    job["created_at"] = created_at
    job["updated_at"] = now

    script_output = (job.get("outputs") or {}).get("script") or {}
    script_content = script_output.get("content") or {}
    title = str(script_content.get("title") or "").strip() or None

    payload = json.dumps(job, ensure_ascii=False, separators=(",", ":"))
    with _LOCK, _connect() as connection:
        connection.execute(
            """
            INSERT INTO jobs (id, status, stage, progress, title, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                stage = excluded.stage,
                progress = excluded.progress,
                title = excluded.title,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (
                job["id"],
                str(job.get("status") or "unknown"),
                str(job.get("stage") or "idea"),
                int(job.get("progress") or 0),
                title,
                payload,
                created_at,
                now,
            ),
        )


def load_jobs() -> dict[str, dict[str, Any]]:
    init_job_store()
    with _LOCK, _connect() as connection:
        rows = connection.execute("SELECT id, payload_json FROM jobs").fetchall()

    loaded: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
            if isinstance(payload, dict):
                loaded[row["id"]] = payload
        except json.JSONDecodeError:
            continue
    return loaded


def list_job_summaries(limit: int = 50) -> list[dict[str, Any]]:
    safe_limit = min(max(int(limit), 1), 200)
    with _LOCK, _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, status, stage, progress, title, created_at, updated_at
            FROM jobs
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def recent_idea_context(limit: int = 30) -> list[str]:
    safe_limit = min(max(int(limit), 1), 100)
    with _LOCK, _connect() as connection:
        rows = connection.execute(
            "SELECT payload_json FROM jobs ORDER BY updated_at DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()

    seen: set[str] = set()
    ideas: list[str] = []
    for row in rows:
        try:
            job = json.loads(row["payload_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = [str((job.get("input") or {}).get("idea_prompt") or "").strip()]
        idea_content = (((job.get("outputs") or {}).get("idea") or {}).get("content") or {})
        script_content = (((job.get("outputs") or {}).get("script") or {}).get("content") or {})
        candidates.extend([
            str(idea_content.get("idea_title") or "").strip(),
            str(idea_content.get("core_idea") or "").strip(),
            str(script_content.get("title") or "").strip(),
        ])
        for candidate in candidates:
            key = " ".join(candidate.lower().split())
            if len(key) < 4 or key in seen:
                continue
            seen.add(key)
            ideas.append(candidate)
    return ideas[:60]


def delete_job(job_id: str) -> None:
    with _LOCK, _connect() as connection:
        connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
