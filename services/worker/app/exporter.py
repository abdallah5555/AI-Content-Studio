from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

EXPORT_ROOT = Path("output/exports")
EXPORT_ROOT.mkdir(parents=True, exist_ok=True)


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

    return {
        "provider": "local-export",
        "export_id": export_id,
        "format": "mp4",
        "filename": filename,
        "size_bytes": destination.stat().st_size,
        "video_path": str(destination),
        "download_url": f"/media/exports/{filename}",
    }
