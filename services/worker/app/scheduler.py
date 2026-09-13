from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/schedule", tags=["schedule"])

DB_PATH = Path(os.getenv("SCHEDULE_DB_PATH", "data/content_schedule.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class ScheduleRequest(BaseModel):
    job_id: str = Field(min_length=2, max_length=200)
    platform: str = Field(min_length=2, max_length=80)
    scheduled_at: str = Field(min_length=10, max_length=80)
    title: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=3000)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def init_schedule_store() -> None:
    with _connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_content (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'planned',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        db.commit()


def _normalize_datetime(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="scheduled_at must be ISO 8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    scheduled = datetime.fromisoformat(item["scheduled_at"])
    now = datetime.now(timezone.utc)
    if item["status"] == "planned" and scheduled <= now:
        item["status"] = "ready"
    return item


init_schedule_store()


@router.get("")
def list_scheduled():
    with _connect() as db:
        rows = db.execute("SELECT * FROM scheduled_content ORDER BY scheduled_at ASC").fetchall()
    return {"items": [_row(row) for row in rows]}


@router.post("")
def create_scheduled(payload: ScheduleRequest):
    item_id = uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    scheduled_at = _normalize_datetime(payload.scheduled_at)
    with _connect() as db:
        db.execute(
            "INSERT INTO scheduled_content (id, job_id, platform, scheduled_at, title, notes, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'planned', ?, ?)",
            (item_id, payload.job_id, payload.platform, scheduled_at, payload.title, payload.notes, now, now),
        )
        db.commit()
        row = db.execute("SELECT * FROM scheduled_content WHERE id = ?", (item_id,)).fetchone()
    return {"item": _row(row)}


@router.patch("/{item_id}/status")
def update_schedule_status(item_id: str, status: str):
    allowed = {"planned", "ready", "published", "cancelled"}
    if status not in allowed:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(allowed)}")
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        cursor = db.execute("UPDATE scheduled_content SET status = ?, updated_at = ? WHERE id = ?", (status, now, item_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Scheduled item not found")
        db.commit()
        row = db.execute("SELECT * FROM scheduled_content WHERE id = ?", (item_id,)).fetchone()
    return {"item": _row(row)}


@router.delete("/{item_id}")
def delete_scheduled(item_id: str):
    with _connect() as db:
        cursor = db.execute("DELETE FROM scheduled_content WHERE id = ?", (item_id,))
        db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Scheduled item not found")
    return {"deleted": True, "id": item_id}
