from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import edge_tts
from fastapi import APIRouter

router = APIRouter(prefix="/tts", tags=["tts"])

OUTPUT_ROOT = Path("tmp/tts_outputs")
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_VOICES = [
    {"id": "ar-EG-SalmaNeural", "label": "سلمى - عربي مصري", "gender": "female", "locale": "ar-EG"},
    {"id": "ar-EG-ShakirNeural", "label": "شاكر - عربي مصري", "gender": "male", "locale": "ar-EG"},
]


@router.get("/voices")
def list_voices():
    return {
        "provider": "edge-tts",
        "requires_api_key": False,
        "voices": DEFAULT_VOICES,
    }


def _extract_script_text(script_result: dict[str, Any]) -> str:
    content = script_result.get("content", {}) if isinstance(script_result, dict) else {}
    if isinstance(content, dict):
        script = content.get("script")
        if isinstance(script, str) and script.strip():
            return script.strip()
        raw = content.get("raw")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    raise RuntimeError("No script text is available for TTS")


async def generate_tts(
    script_result: dict[str, Any],
    *,
    voice: str | None = None,
    rate: str | None = None,
) -> dict[str, Any]:
    text = _extract_script_text(script_result)
    selected_voice = voice or os.getenv("TTS_VOICE", "ar-EG-SalmaNeural")
    selected_rate = rate or os.getenv("TTS_RATE", "+0%")

    audio_id = uuid4().hex
    destination = OUTPUT_ROOT / f"{audio_id}.mp3"

    communicate = edge_tts.Communicate(
        text=text,
        voice=selected_voice,
        rate=selected_rate,
    )
    await communicate.save(str(destination))

    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("TTS provider did not produce an audio file")

    return {
        "provider": "edge-tts",
        "audio_id": audio_id,
        "voice": selected_voice,
        "rate": selected_rate,
        "format": "mp3",
        "size_bytes": destination.stat().st_size,
        "file_path": str(destination),
        "text_length": len(text),
    }
