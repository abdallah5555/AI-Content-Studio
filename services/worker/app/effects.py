from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

EFFECTS_ROOT = Path("output/effects")
WORK_ROOT = Path("tmp/effects_jobs")
EFFECTS_ROOT.mkdir(parents=True, exist_ok=True)
WORK_ROOT.mkdir(parents=True, exist_ok=True)


def _ffmpeg_binary() -> str:
    binary = os.getenv("FFMPEG_BINARY", "ffmpeg")
    if not shutil.which(binary):
        raise RuntimeError("FFmpeg is not installed or FFMPEG_BINARY is invalid")
    return binary


def _run(args: list[str], timeout: int = 600) -> None:
    process = subprocess.run(
        [_ffmpeg_binary(), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "FFmpeg failed")[-2500:]
        raise RuntimeError(detail)


def _probe_duration(path: Path) -> float | None:
    ffprobe = os.getenv("FFPROBE_BINARY", "ffprobe")
    if not shutil.which(ffprobe):
        return None
    process = subprocess.run(
        [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if process.returncode != 0:
        return None
    try:
        data = json.loads(process.stdout)
        return float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def _escape_ass_text(text: str) -> str:
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("\n", r"\N")
    )


def _build_ass(selections: list[dict[str, Any]], destination: Path, width: int, height: int) -> int:
    font_size = 56 if height >= 1500 else 42
    margin_v = max(60, int(height * 0.08))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,DejaVu Sans,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,70,70,{margin_v},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [header]
    cursor = 0.0
    count = 0
    for index, selection in enumerate(selections, start=1):
        try:
            seconds = float(selection.get("seconds") or 4.0)
        except (TypeError, ValueError):
            seconds = 4.0
        seconds = min(max(seconds, 1.0), 30.0)
        caption = str(selection.get("caption") or "").strip()
        if caption:
            start = cursor
            end = cursor + seconds
            lines.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{_escape_ass_text(caption)}\n"
            )
            count += 1
        cursor += seconds

    destination.write_text("".join(lines), encoding="utf-8-sig")
    return count


def _escape_filter_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", r"\:").replace("'", r"\'")
    return value


def apply_effects(
    edit_result: dict[str, Any],
    media_result: dict[str, Any],
) -> dict[str, Any]:
    source_raw = edit_result.get("video_path")
    if not source_raw:
        raise RuntimeError("Edit stage did not return a local video_path")
    source = Path(source_raw)
    if not source.exists():
        raise RuntimeError("Edited video is missing from the worker")

    width = int(edit_result.get("width") or 1080)
    height = int(edit_result.get("height") or 1920)
    selections = (media_result.get("content") or {}).get("selections") or []
    if not isinstance(selections, list):
        selections = []

    effects_id = uuid4().hex
    work_dir = WORK_ROOT / effects_id
    work_dir.mkdir(parents=True, exist_ok=True)
    output = EFFECTS_ROOT / f"{effects_id}.mp4"
    ass_file = work_dir / "captions.ass"

    captions_count = _build_ass(selections, ass_file, width, height)
    duration = _probe_duration(source)

    filters: list[str] = []
    if captions_count:
        filters.append(f"ass='{_escape_filter_path(ass_file)}':shaping=complex")
    if duration and duration > 1.2:
        filters.append("fade=t=in:st=0:d=0.25")
        filters.append(f"fade=t=out:st={max(duration - 0.35, 0):.3f}:d=0.35")

    captions_burned = captions_count > 0
    warning = None

    try:
        args = ["-y", "-i", str(source)]
        if filters:
            args += ["-vf", ",".join(filters)]
        args += [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "21",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output),
        ]
        _run(args)
    except Exception as exc:
        if not captions_count:
            raise

        captions_burned = False
        warning = f"Caption burn-in failed; video kept without captions: {str(exc)[:300]}"
        fallback_filters = [item for item in filters if not item.startswith("ass=")]
        args = ["-y", "-i", str(source)]
        if fallback_filters:
            args += ["-vf", ",".join(fallback_filters)]
            args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21"]
        else:
            args += ["-c:v", "copy"]
        args += ["-c:a", "copy", "-movflags", "+faststart", str(output)]
        _run(args)

    return {
        "provider": "ffmpeg",
        "effects_id": effects_id,
        "format": "mp4",
        "size_bytes": output.stat().st_size,
        "video_path": str(output),
        "video_url": f"/media/effects/{effects_id}.mp4",
        "captions_count": captions_count,
        "captions_burned": captions_burned,
        "fade_applied": bool(duration and duration > 1.2),
        "warning": warning,
    }
