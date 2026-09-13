from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

DB_PATH = Path(os.getenv("INTELLIGENCE_DB_PATH", "data/content_intelligence.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_intelligence_store() -> None:
    with _connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS trend_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trend_key TEXT NOT NULL,
                geo TEXT NOT NULL,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                traffic INTEGER NOT NULL DEFAULT 0,
                score REAL NOT NULL DEFAULT 0,
                lifecycle TEXT NOT NULL DEFAULT 'new',
                payload_json TEXT NOT NULL,
                captured_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_trend_snapshots_key_geo_time
                ON trend_snapshots(trend_key, geo, captured_at DESC);

            CREATE TABLE IF NOT EXISTS trend_watchlist (
                trend_key TEXT PRIMARY KEY,
                geo TEXT NOT NULL,
                title TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS idea_inbox (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'new',
                score REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS brand_profiles (
                profile_key TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS content_performance (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                platform TEXT,
                views INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                shares INTEGER NOT NULL DEFAULT 0,
                duration_seconds REAL,
                hook TEXT,
                content_type TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )


def save_trend_snapshot(item: dict[str, Any], geo: str) -> None:
    now = _utc_now()
    with _connect() as db:
        db.execute(
            """
            INSERT INTO trend_snapshots
                (trend_key, geo, title, source, traffic, score, lifecycle, payload_json, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["key"], geo, item["title"], item.get("source", "unknown"),
                int(item.get("traffic", 0)), float(item.get("score", 0)),
                item.get("lifecycle", "new"), json.dumps(item, ensure_ascii=False), now,
            ),
        )


def previous_trend_snapshot(trend_key: str, geo: str) -> dict[str, Any] | None:
    with _connect() as db:
        row = db.execute(
            """
            SELECT payload_json, traffic, score, captured_at
            FROM trend_snapshots
            WHERE trend_key = ? AND geo = ?
            ORDER BY captured_at DESC LIMIT 1
            """,
            (trend_key, geo),
        ).fetchone()
    if not row:
        return None
    payload = json.loads(row["payload_json"])
    payload["captured_at"] = row["captured_at"]
    return payload


def add_watchlist(item: dict[str, Any], geo: str) -> dict[str, Any]:
    now = _utc_now()
    with _connect() as db:
        db.execute(
            """
            INSERT INTO trend_watchlist (trend_key, geo, title, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(trend_key) DO UPDATE SET
                geo = excluded.geo,
                title = excluded.title,
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (item["key"], geo, item["title"], json.dumps(item, ensure_ascii=False), now, now),
        )
    return item


def list_watchlist() -> list[dict[str, Any]]:
    with _connect() as db:
        rows = db.execute(
            "SELECT trend_key, geo, title, payload_json, created_at, updated_at FROM trend_watchlist ORDER BY updated_at DESC"
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload.update({"geo": row["geo"], "watched_at": row["created_at"], "watch_updated_at": row["updated_at"]})
        items.append(payload)
    return items


def remove_watchlist(trend_key: str) -> bool:
    with _connect() as db:
        cursor = db.execute("DELETE FROM trend_watchlist WHERE trend_key = ?", (trend_key,))
    return cursor.rowcount > 0


def add_idea(text: str, tags: list[str] | None = None) -> dict[str, Any]:
    idea_id = uuid4().hex
    now = _utc_now()
    record = {"id": idea_id, "text": text, "tags": tags or [], "status": "new", "score": None, "created_at": now, "updated_at": now}
    with _connect() as db:
        db.execute(
            "INSERT INTO idea_inbox (id, text, tags_json, status, score, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (idea_id, text, json.dumps(tags or [], ensure_ascii=False), "new", None, now, now),
        )
    return record


def list_ideas(limit: int = 100) -> list[dict[str, Any]]:
    with _connect() as db:
        rows = db.execute(
            "SELECT id, text, tags_json, status, score, created_at, updated_at FROM idea_inbox ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"], "text": row["text"], "tags": json.loads(row["tags_json"]),
            "status": row["status"], "score": row["score"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def delete_idea(idea_id: str) -> bool:
    with _connect() as db:
        cursor = db.execute("DELETE FROM idea_inbox WHERE id = ?", (idea_id,))
    return cursor.rowcount > 0


def save_brand_profile(payload: dict[str, Any], profile_key: str = "default") -> dict[str, Any]:
    now = _utc_now()
    with _connect() as db:
        db.execute(
            """
            INSERT INTO brand_profiles (profile_key, payload_json, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(profile_key) DO UPDATE SET payload_json = excluded.payload_json, updated_at = excluded.updated_at
            """,
            (profile_key, json.dumps(payload, ensure_ascii=False), now),
        )
    return {"profile_key": profile_key, "profile": payload, "updated_at": now}


def get_brand_profile(profile_key: str = "default") -> dict[str, Any]:
    with _connect() as db:
        row = db.execute("SELECT payload_json, updated_at FROM brand_profiles WHERE profile_key = ?", (profile_key,)).fetchone()
    if not row:
        return {"profile_key": profile_key, "profile": {}, "updated_at": None}
    return {"profile_key": profile_key, "profile": json.loads(row["payload_json"]), "updated_at": row["updated_at"]}


def add_performance(payload: dict[str, Any]) -> dict[str, Any]:
    item_id = uuid4().hex
    now = _utc_now()
    record = {"id": item_id, **payload, "created_at": now}
    with _connect() as db:
        db.execute(
            """
            INSERT INTO content_performance
                (id, title, platform, views, likes, comments, shares, duration_seconds, hook, content_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item_id, str(payload.get("title") or "Untitled"), payload.get("platform"),
                int(payload.get("views") or 0), int(payload.get("likes") or 0), int(payload.get("comments") or 0),
                int(payload.get("shares") or 0), payload.get("duration_seconds"), payload.get("hook"), payload.get("content_type"),
                json.dumps(payload, ensure_ascii=False), now,
            ),
        )
    return record


def list_performance(limit: int = 200) -> list[dict[str, Any]]:
    with _connect() as db:
        rows = db.execute("SELECT payload_json, id, created_at FROM content_performance ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    items = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload.update({"id": row["id"], "created_at": row["created_at"]})
        items.append(payload)
    return items


init_intelligence_store()
