from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .supabase_rest import configured as supabase_configured
from .supabase_rest import delete as supabase_delete
from .supabase_rest import insert as supabase_insert
from .supabase_rest import select as supabase_select
from .supabase_rest import upsert as supabase_upsert

DB_PATH = Path(os.getenv("INTELLIGENCE_DB_PATH", "data/content_intelligence.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_intelligence_store() -> None:
    if supabase_configured():
        return
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
    if supabase_configured():
        supabase_insert("content_studio_trend_snapshots", {"trend_key": item["key"], "geo": geo, "observed_at": now, "payload": item})
        return
    with _connect() as db:
        db.execute(
            "INSERT INTO trend_snapshots (trend_key, geo, title, source, traffic, score, lifecycle, payload_json, captured_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item["key"], geo, item["title"], item.get("source", "unknown"), int(item.get("traffic", 0)), float(item.get("score", 0)), item.get("lifecycle", "new"), json.dumps(item, ensure_ascii=False), now),
        )


def previous_trend_snapshot(trend_key: str, geo: str) -> dict[str, Any] | None:
    if supabase_configured():
        rows = supabase_select(
            "content_studio_trend_snapshots",
            columns="payload,observed_at",
            filters={"trend_key": f"eq.{trend_key}", "geo": f"eq.{geo}"},
            order="observed_at.desc",
            limit=1,
        )
        if not rows:
            return None
        payload = dict(rows[0].get("payload") or {})
        payload["captured_at"] = rows[0].get("observed_at")
        return payload
    with _connect() as db:
        row = db.execute("SELECT payload_json, captured_at FROM trend_snapshots WHERE trend_key = ? AND geo = ? ORDER BY captured_at DESC LIMIT 1", (trend_key, geo)).fetchone()
    if not row:
        return None
    payload = json.loads(row["payload_json"])
    payload["captured_at"] = row["captured_at"]
    return payload


def add_watchlist(item: dict[str, Any], geo: str) -> dict[str, Any]:
    now = _utc_now()
    if supabase_configured():
        supabase_upsert("content_studio_watchlist", {"trend_key": item["key"], "geo": geo, "trend": item, "watched_at": now}, on_conflict="trend_key")
        return item
    with _connect() as db:
        db.execute(
            "INSERT INTO trend_watchlist (trend_key, geo, title, payload_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(trend_key) DO UPDATE SET geo = excluded.geo, title = excluded.title, payload_json = excluded.payload_json, updated_at = excluded.updated_at",
            (item["key"], geo, item["title"], json.dumps(item, ensure_ascii=False), now, now),
        )
    return item


def list_watchlist() -> list[dict[str, Any]]:
    if supabase_configured():
        rows = supabase_select("content_studio_watchlist", order="watched_at.desc")
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row.get("trend") or {})
            payload.update({"geo": row.get("geo"), "watched_at": row.get("watched_at"), "watch_updated_at": row.get("watched_at")})
            items.append(payload)
        return items
    with _connect() as db:
        rows = db.execute("SELECT trend_key, geo, title, payload_json, created_at, updated_at FROM trend_watchlist ORDER BY updated_at DESC").fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload.update({"geo": row["geo"], "watched_at": row["created_at"], "watch_updated_at": row["updated_at"]})
        items.append(payload)
    return items


def remove_watchlist(trend_key: str) -> bool:
    if supabase_configured():
        rows = supabase_select("content_studio_watchlist", columns="trend_key", filters={"trend_key": f"eq.{trend_key}"}, limit=1)
        if not rows:
            return False
        supabase_delete("content_studio_watchlist", {"trend_key": f"eq.{trend_key}"})
        return True
    with _connect() as db:
        cursor = db.execute("DELETE FROM trend_watchlist WHERE trend_key = ?", (trend_key,))
    return cursor.rowcount > 0


def add_idea(text: str, tags: list[str] | None = None) -> dict[str, Any]:
    idea_id = str(uuid4())
    now = _utc_now()
    record = {"id": idea_id, "text": text, "tags": tags or [], "status": "new", "score": None, "created_at": now, "updated_at": now}
    if supabase_configured():
        supabase_upsert("content_studio_ideas", record, on_conflict="id")
        return record
    with _connect() as db:
        db.execute("INSERT INTO idea_inbox (id, text, tags_json, status, score, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (idea_id, text, json.dumps(tags or [], ensure_ascii=False), "new", None, now, now))
    return record


def list_ideas(limit: int = 100) -> list[dict[str, Any]]:
    if supabase_configured():
        return supabase_select("content_studio_ideas", order="updated_at.desc", limit=limit)
    with _connect() as db:
        rows = db.execute("SELECT id, text, tags_json, status, score, created_at, updated_at FROM idea_inbox ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": row["id"], "text": row["text"], "tags": json.loads(row["tags_json"]), "status": row["status"], "score": row["score"], "created_at": row["created_at"], "updated_at": row["updated_at"]} for row in rows]


def delete_idea(idea_id: str) -> bool:
    if supabase_configured():
        rows = supabase_select("content_studio_ideas", columns="id", filters={"id": f"eq.{idea_id}"}, limit=1)
        if not rows:
            return False
        supabase_delete("content_studio_ideas", {"id": f"eq.{idea_id}"})
        return True
    with _connect() as db:
        cursor = db.execute("DELETE FROM idea_inbox WHERE id = ?", (idea_id,))
    return cursor.rowcount > 0


def save_brand_profile(payload: dict[str, Any], profile_key: str = "default") -> dict[str, Any]:
    now = _utc_now()
    if supabase_configured():
        supabase_upsert("content_studio_brand_profile", {"singleton": True, "profile": payload, "updated_at": now}, on_conflict="singleton")
        return {"profile_key": profile_key, "profile": payload, "updated_at": now}
    with _connect() as db:
        db.execute("INSERT INTO brand_profiles (profile_key, payload_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(profile_key) DO UPDATE SET payload_json = excluded.payload_json, updated_at = excluded.updated_at", (profile_key, json.dumps(payload, ensure_ascii=False), now))
    return {"profile_key": profile_key, "profile": payload, "updated_at": now}


def get_brand_profile(profile_key: str = "default") -> dict[str, Any]:
    if supabase_configured():
        rows = supabase_select("content_studio_brand_profile", columns="profile,updated_at", filters={"singleton": "eq.true"}, limit=1)
        if not rows:
            return {"profile_key": profile_key, "profile": {}, "updated_at": None}
        return {"profile_key": profile_key, "profile": rows[0].get("profile") or {}, "updated_at": rows[0].get("updated_at")}
    with _connect() as db:
        row = db.execute("SELECT payload_json, updated_at FROM brand_profiles WHERE profile_key = ?", (profile_key,)).fetchone()
    if not row:
        return {"profile_key": profile_key, "profile": {}, "updated_at": None}
    return {"profile_key": profile_key, "profile": json.loads(row["payload_json"]), "updated_at": row["updated_at"]}


def add_performance(payload: dict[str, Any]) -> dict[str, Any]:
    item_id = str(uuid4())
    now = _utc_now()
    record = {"id": item_id, **payload, "created_at": now}
    if supabase_configured():
        supabase_upsert(
            "content_studio_performance",
            {
                "id": item_id,
                "title": str(payload.get("title") or "Untitled"),
                "platform": payload.get("platform"),
                "views": int(payload.get("views") or 0),
                "likes": int(payload.get("likes") or 0),
                "comments": int(payload.get("comments") or 0),
                "shares": int(payload.get("shares") or 0),
                "duration_seconds": payload.get("duration_seconds"),
                "hook": payload.get("hook"),
                "content_type": payload.get("content_type"),
                "notes": payload.get("notes"),
                "created_at": now,
            },
            on_conflict="id",
        )
        return record
    with _connect() as db:
        db.execute(
            "INSERT INTO content_performance (id, title, platform, views, likes, comments, shares, duration_seconds, hook, content_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, str(payload.get("title") or "Untitled"), payload.get("platform"), int(payload.get("views") or 0), int(payload.get("likes") or 0), int(payload.get("comments") or 0), int(payload.get("shares") or 0), payload.get("duration_seconds"), payload.get("hook"), payload.get("content_type"), json.dumps(payload, ensure_ascii=False), now),
        )
    return record


def list_performance(limit: int = 200) -> list[dict[str, Any]]:
    if supabase_configured():
        return supabase_select("content_studio_performance", order="created_at.desc", limit=limit)
    with _connect() as db:
        rows = db.execute("SELECT payload_json, id, created_at FROM content_performance ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    items = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload.update({"id": row["id"], "created_at": row["created_at"]})
        items.append(payload)
    return items


init_intelligence_store()
