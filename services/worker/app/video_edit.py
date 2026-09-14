from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from uuid import uuid4

RENDER_ROOT = Path("output/renders")
WORK_ROOT = Path("tmp/render_jobs")
RENDER_ROOT.mkdir(parents=True, exist_ok=True)
WORK_ROOT.mkdir(parents=True, exist_ok=True)

MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024

TARGETS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}


def ffmpeg_available() -> bool:
    binary = os.getenv("FFMPEG_BINARY", "ffmpeg")
    return bool(shutil.which(binary))


def _run_ffmpeg(args: list[str]) -> None:
    binary = os.getenv("FFMPEG_BINARY", "ffmpeg")
    if not shutil.which(binary):
        raise RuntimeError("FFmpeg is not installed or FFMPEG_BINARY is invalid")

    process = subprocess.run(
        [binary, "-threads", "2", "-filter_threads", "2", *args],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if process.returncode != 0:
        error = (process.stderr or process.stdout or "FFmpeg failed")[-2500:]
        raise RuntimeError(f"FFmpeg failed: {error}")


def _download(url: str, destination: Path) -> None:
    req = urllib_request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
        },
        method="GET",
    )
    total = 0
    try:
        with urllib_request.urlopen(req, timeout=90) as response, destination.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError("Selected media file exceeds 300 MB download limit")
                handle.write(chunk)
    except HTTPError as exc:
        raise RuntimeError(f"Media download failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Media download failed: {exc.reason}") from exc


def _safe_seconds(value: Any, default: float = 4.0) -> float:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(seconds, 1.0), 30.0)


def _normalize_segment(source: Path, destination: Path, seconds: float, width: int, height: int) -> None:
    filter_graph = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps=30"
    )
    _run_ffmpeg([
        "-y",
        "-stream_loop", "-1",
        "-i", str(source),
        "-t", f"{seconds:.3f}",
        "-an",
        "-vf", filter_graph,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(destination),
    ])


def _concat_segments(segments: list[Path], output: Path, work_dir: Path) -> None:
    list_file = work_dir / "concat.txt"
    lines = []
    for segment in segments:
        escaped = str(segment.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _run_ffmpeg([
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output),
    ])


def _attach_voice(video: Path, audio: Path, output: Path) -> None:
    _run_ffmpeg([
        "-y",
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ])


def render_montage(
    media_result: dict[str, Any],
    tts_result: dict[str, Any],
    aspect_ratio: str,
) -> dict[str, Any]:
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg is required for the edit stage but was not found")

    selections = (media_result.get("content") or {}).get("selections") or []
    if not isinstance(selections, list) or not selections:
        raise RuntimeError("Media stage returned no selected scenes")

    audio_path_raw = tts_result.get("audio_path") or tts_result.get("file_path")
    if not audio_path_raw:
        raise RuntimeError("TTS stage returned no local audio path")
    audio_path = Path(audio_path_raw)
    if not audio_path.exists():
        raise RuntimeError("TTS audio file is missing from the worker")

    width, height = TARGETS.get(aspect_ratio, TARGETS["9:16"])
    render_id = uuid4().hex
    work_dir = WORK_ROOT / render_id
    work_dir.mkdir(parents=True, exist_ok=True)

    normalized: list[Path] = []
    scene_manifest: list[dict[str, Any]] = []

    try:
        for index, selection in enumerate(selections, start=1):
            media = selection.get("media") or {}
            download_url = str(media.get("download_url") or "").strip()
            if not download_url:
                raise RuntimeError(f"Scene {index} has no downloadable media URL")

            source = work_dir / f"source-{index:03d}.mp4"
            segment = work_dir / f"segment-{index:03d}.mp4"
            seconds = _safe_seconds(selection.get("seconds"))

            _download(download_url, source)
            _normalize_segment(source, segment, seconds, width, height)
            normalized.append(segment)
            scene_manifest.append({
                "scene": selection.get("scene", index),
                "seconds": seconds,
                "provider": media.get("provider"),
                "media_id": media.get("id"),
                "query": selection.get("search_query"),
            })

        video_track = work_dir / "video-track.mp4"
        _concat_segments(normalized, video_track, work_dir)

        output = RENDER_ROOT / f"{render_id}.mp4"
        _attach_voice(video_track, audio_path, output)

        return {
            "provider": "ffmpeg",
            "render_id": render_id,
            "format": "mp4",
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "size_bytes": output.stat().st_size,
            "video_path": str(output),
            "video_url": f"/media/renders/{render_id}.mp4",
            "scene_manifest": scene_manifest,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
