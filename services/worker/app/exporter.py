from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from .supabase_rest import configured as supabase_configured
from .supabase_rest import create_signed_url, upload_file

EXPORT_ROOT = Path("output/exports")
EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
EXPORT_BUCKET = "content-studio-exports"


def _safe_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\-\u0600-\u06FF]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:80] or "video"


def export_video(
    source_result: dict[str, Any],
    script_result: dict[str, Any],
) -> dict[str, Any]:
    source_raw = source_result.get("video_path")
    if not source_raw:
        raise RuntimeError("No source video_path was provided to the export stage")
    source = Path(source_raw)
    if not source.exists():
        raise RuntimeError("Source video is missing from the worker")

    script_content = script_result.get("content") or {}
    title = str(script_content.get("title") or "video")
    export_id = uuid4().hex
    filename = f"{_safe_slug(title)}-{export_id[:8]}.mp4"
    destination = EXPORT_ROOT / filename
    shutil.copy2(source, destination)

    storage_path = None
    download_url = f"/media/exports/{filename}"
    provider = "local-export"
    if supabase_configured():
        object_path = f"exports/{filename}"
        storage_path = upload_file(EXPORT_BUCKET, object_path, destination, content_type="video/mp4")
        download_url = create_signed_url(EXPORT_BUCKET, object_path, expires_in=3600, download_name=filename)
        provider = "supabase-storage"

    media_attributions = [item for item in (script_result.get("media_attributions") or []) if isinstance(item, dict)]
    music_track = str(source_result.get("track") or "").strip() or None
    music_applied = bool(source_result.get("music_applied"))

    return {
        "provider": provider,
        "export_id": export_id,
        "format": "mp4",
        "filename": filename,
        "size_bytes": destination.stat().st_size,
        "video_path": str(destination),
        "download_url": download_url,
        "storage_path": storage_path,
        "attributions": media_attributions,
        "music": {
            "applied": music_applied,
            "track": music_track,
            "source": "user/local royalty-free library" if music_applied else None,
        },
    }
