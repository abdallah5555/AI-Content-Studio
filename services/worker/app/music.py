from __future__ import annotations

import os
import random
import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from .scheduler import router as scheduler_router

router = APIRouter(prefix="/music", tags=["music"])

MUSIC_LIBRARY_ROOT = Path(os.getenv("MUSIC_LIBRARY_DIR", "assets/music"))
MUSIC_OUTPUT_ROOT = Path("output/music")
MUSIC_LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
MUSIC_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_MUSIC_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
MAX_MUSIC_BYTES = 80 * 1024 * 1024


def _ffmpeg_binary() -> str:
    binary = os.getenv("FFMPEG_BINARY", "ffmpeg")
    if not shutil.which(binary):
        raise RuntimeError("FFmpeg is not installed or FFMPEG_BINARY is invalid")
    return binary


def list_music_tracks() -> list[Path]:
    tracks = []
    for path in MUSIC_LIBRARY_ROOT.iterdir():
        if path.is_file() and path.suffix.lower() in ALLOWED_MUSIC_SUFFIXES:
            tracks.append(path)
    return sorted(tracks)


@router.get("/library")
def get_music_library():
    tracks = list_music_tracks()
    return {
        "count": len(tracks),
        "tracks": [{"name": path.name, "size_bytes": path.stat().st_size} for path in tracks],
    }


@router.post("/library")
async def upload_music(file: UploadFile = File(...)):
    suffix = Path(file.filename or "track").suffix.lower()
    if suffix not in ALLOWED_MUSIC_SUFFIXES:
        raise HTTPException(status_code=415, detail="Unsupported music file type")

    data = await file.read(MAX_MUSIC_BYTES + 1)
    if len(data) > MAX_MUSIC_BYTES:
        raise HTTPException(status_code=413, detail="Music file is larger than 80 MB")

    track_id = uuid4().hex
    destination = MUSIC_LIBRARY_ROOT / f"{track_id}{suffix}"
    destination.write_bytes(data)
    return {
        "id": track_id,
        "name": file.filename or destination.name,
        "stored_name": destination.name,
        "size_bytes": len(data),
    }


def mix_background_music(
    source_result: dict[str, Any],
    volume: float = 0.12,
) -> dict[str, Any]:
    source_raw = source_result.get("video_path")
    if not source_raw:
        raise RuntimeError("Previous stage did not return a local video_path")
    source = Path(source_raw)
    if not source.exists():
        raise RuntimeError("Source video is missing from the worker")

    tracks = list_music_tracks()
    output_id = uuid4().hex
    output = MUSIC_OUTPUT_ROOT / f"{output_id}.mp4"

    if not tracks:
        shutil.copy2(source, output)
        return {
            "provider": "local-library",
            "status": "skipped",
            "reason": "No royalty-free music tracks are available in the local library",
            "music_applied": False,
            "video_path": str(output),
            "video_url": f"/media/music/{output_id}.mp4",
            "size_bytes": output.stat().st_size,
        }

    track = random.choice(tracks)
    safe_volume = min(max(float(volume), 0.0), 0.5)
    filter_graph = (
        f"[1:a]volume={safe_volume:.3f}[music];"
        "[0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
    process = subprocess.run(
        [
            _ffmpeg_binary(),
            "-y",
            "-i", str(source),
            "-stream_loop", "-1",
            "-i", str(track),
            "-filter_complex", filter_graph,
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "Music mix failed")[-2500:]
        raise RuntimeError(f"Music mix failed: {detail}")

    return {
        "provider": "local-library",
        "status": "mixed",
        "music_applied": True,
        "track": track.name,
        "volume": safe_volume,
        "video_path": str(output),
        "video_url": f"/media/music/{output_id}.mp4",
        "size_bytes": output.stat().st_size,
    }


# The main worker already mounts this router. Extending it with the scheduler
# routes keeps the scheduler registered without duplicating route wiring in
# multiple application entry points.
router.routes.extend(scheduler_router.routes)
