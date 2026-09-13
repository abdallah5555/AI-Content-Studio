from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from .supabase_rest import configured as supabase_configured
from .supabase_rest import create_signed_url
from .supabase_rest import delete as supabase_delete
from .supabase_rest import select as supabase_select
from .supabase_rest import upsert as supabase_upsert

DB_PATH = Path(os.getenv("JOB_DB_PATH", "data/ai_content_studio.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_LOCK = Lock()
EXPORT_BUCKET = "content-studio-exports"
EXPORT_LINK_TTL = 7 * 24 * 60 * 60


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def init_job_store() -> None:
    if supabase_configured():
        return
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


def _job_title(job: dict[str, Any]) -> str | None:
    script_output = (job.get("outputs") or {}).get("script") or {}
    script_content = script_output.get("content") or {}
    return str(script_content.get("title") or "").strip() or None


def _refresh_export_url(job: dict[str, Any]) -> dict[str, Any]:
    if not supabase_configured():
        return job
    export = ((job.get("outputs") or {}).get("export") or {})
    storage_path = str(export.get("storage_path") or "")
    filename = str(export.get("filename") or "")
    prefix = f"{EXPORT_BUCKET}/"
    if not storage_path.startswith(prefix) or not filename:
        return job
    object_path = storage_path[len(prefix):]
    try:
        export["download_url"] = create_signed_url(EXPORT_BUCKET, object_path, expires_in=EXPORT_LINK_TTL, download_name=filename)
    except Exception:
        pass
    return job


def save_job(job: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    created_at = str(job.get("created_at") or now)
    job["created_at"] = created_at
    job["updated_at"] = now
    title = _job_title(job)

    if supabase_configured():
        supabase_upsert(
            "content_studio_jobs",
            {
                "id": job["id"],
                "status": str(job.get("status") or "unknown"),
                "stage": str(job.get("stage") or "idea"),
                "progress": int(job.get("progress") or 0),
                "title": title,
                "payload": job,
                "created_at": created_at,
                "updated_at": now,
            },
            on_conflict="id",
        )
        return

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
            (job["id"], str(job.get("status") or "unknown"), str(job.get("stage") or "idea"), int(job.get("progress") or 0), title, payload, created_at, now),
        )


def load_jobs() -> dict[str, dict[str, Any]]:
    if supabase_configured():
        rows = supabase_select("content_studio_jobs", columns="id,payload")
        loaded: dict[str, dict[str, Any]] = {}
        for row in rows:
            payload = row.get("payload")
            if isinstance(payload, dict):
                loaded[str(row["id"])] = _refresh_export_url(payload)
        return loaded

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
    if supabase_configured():
        return supabase_select(
            "content_studio_jobs",
            columns="id,status,stage,progress,title,created_at,updated_at",
            order="updated_at.desc",
            limit=safe_limit,
        )
    with _LOCK, _connect() as connection:
        rows = connection.execute(
            "SELECT id, status, stage, progress, title, created_at, updated_at FROM jobs ORDER BY updated_at DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def recent_idea_context(limit: int = 30) -> list[str]:
    safe_limit = min(max(int(limit), 1), 100)
    if supabase_configured():
        rows = supabase_select("content_studio_jobs", columns="payload", order="updated_at.desc", limit=safe_limit)
        jobs_payload = [row.get("payload") for row in rows if isinstance(row.get("payload"), dict)]
    else:
        with _LOCK, _connect() as connection:
            rows = connection.execute("SELECT payload_json FROM jobs ORDER BY updated_at DESC LIMIT ?", (safe_limit,)).fetchall()
        jobs_payload = []
        for row in rows:
            try:
                jobs_payload.append(json.loads(row["payload_json"]))
            except (json.JSONDecodeError, TypeError):
                continue

    seen: set[str] = set()
    ideas: list[str] = []
    for job in jobs_payload:
        if not isinstance(job, dict):
            continue
        candidates = [str((job.get("input") or {}).get("idea_prompt") or "").strip()]
        idea_content = (((job.get("outputs") or {}).get("idea") or {}).get("content") or {})
        script_content = (((job.get("outputs") or {}).get("script") or {}).get("content") or {})
        candidates.extend([str(idea_content.get("idea_title") or "").strip(), str(idea_content.get("core_idea") or "").strip(), str(script_content.get("title") or "").strip()])
        for candidate in candidates:
            key = " ".join(candidate.lower().split())
            if len(key) < 4 or key in seen:
                continue
            seen.add(key)
            ideas.append(candidate)
    return ideas[:60]


def delete_job(job_id: str) -> None:
    if supabase_configured():
        supabase_delete("content_studio_jobs", {"id": f"eq.{job_id}"})
        return
    with _LOCK, _connect() as connection:
        connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
