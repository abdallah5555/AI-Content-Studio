from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/references", tags=["references"])

UPLOAD_ROOT = Path("tmp/reference_uploads")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
MAX_REFERENCE_BYTES = 100 * 1024 * 1024
ALLOWED_PREFIXES = ("image/", "video/")


class ReferenceUploadResult(BaseModel):
    id: str
    name: str
    kind: Literal["image", "video"]
    mime_type: str
    size_bytes: int
    sha256: str
    analysis_status: Literal["queued", "analyzing", "ready", "failed"] = "queued"
    analysis: dict[str, Any] | None = None
    analysis_error: str | None = None


REFERENCE_FILES: dict[str, ReferenceUploadResult] = {}
REFERENCE_PATHS: dict[str, Path] = {}


def _clean_json_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _analysis_prompt(kind: str) -> str:
    motion_instruction = (
        "Analyze camera movement, subject movement, pacing, transition rhythm and shot changes."
        if kind == "video"
        else "For motion fields, infer only what would fit this still image and clearly mark it as inferred."
    )
    return f"""
You are the visual-reference analyst inside an AI social-content production app.
Analyze this {kind} as a REFERENCE, not as content to copy.
The user will later provide a completely different idea and wants the new output to preserve selected visual traits.

{motion_instruction}

Return JSON only with these keys:
- style_summary: concise description of the visual style
- palette: array of dominant color descriptions
- composition: framing, perspective, layout, depth, subject placement
- lighting: lighting style and contrast
- texture_materials: notable surfaces/materials/rendering traits
- character_object_design: shapes, proportions, facial/object treatment, recurring design language
- motion: camera movement, subject movement and pacing when applicable
- editing_rhythm: cut/transition rhythm when applicable
- typography: visible text/caption treatment if any
- reusable_traits: array of traits safe to carry into a new idea
- avoid_copying: array describing elements that should NOT be copied literally
- generation_guidance: a practical prompt paragraph for recreating the same visual spirit on a new idea

Do not identify or imitate a living artist. Describe observable visual properties instead.
""".strip()


def _analyze_with_gemini(reference_id: str) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed") from exc

    result = REFERENCE_FILES[reference_id]
    path = REFERENCE_PATHS[reference_id]
    model = os.getenv("GEMINI_VISION_MODEL", "gemini-3.8-flash")

    client = genai.Client(api_key=api_key)
    uploaded = client.files.upload(file=str(path))
    interaction = client.interactions.create(
        model=model,
        input=[
            {"type": "text", "text": _analysis_prompt(result.kind)},
            {
                "type": result.kind,
                "uri": uploaded.uri,
                "mime_type": result.mime_type,
            },
        ],
    )

    raw_text = interaction.output_text or ""
    if not raw_text.strip():
        raise RuntimeError("Vision provider returned an empty analysis")

    cleaned = _clean_json_text(raw_text)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return {
        "style_summary": raw_text.strip(),
        "reusable_traits": [],
        "avoid_copying": [],
        "generation_guidance": raw_text.strip(),
    }


@router.post("", response_model=ReferenceUploadResult)
async def upload_reference(file: UploadFile = File(...)):
    mime_type = file.content_type or "application/octet-stream"
    if not mime_type.startswith(ALLOWED_PREFIXES):
        raise HTTPException(status_code=415, detail="Only image or video references are supported")

    data = await file.read(MAX_REFERENCE_BYTES + 1)
    if len(data) > MAX_REFERENCE_BYTES:
        raise HTTPException(status_code=413, detail="Reference file is larger than 100 MB")

    reference_id = uuid4().hex
    suffix = Path(file.filename or "reference").suffix[:12]
    destination = UPLOAD_ROOT / f"{reference_id}{suffix}"
    destination.write_bytes(data)

    result = ReferenceUploadResult(
        id=reference_id,
        name=file.filename or "reference",
        kind="video" if mime_type.startswith("video/") else "image",
        mime_type=mime_type,
        size_bytes=len(data),
        sha256=sha256(data).hexdigest(),
        analysis_status="queued",
    )
    REFERENCE_FILES[reference_id] = result
    REFERENCE_PATHS[reference_id] = destination
    return result


@router.post("/{reference_id}/analyze", response_model=ReferenceUploadResult)
def analyze_reference(reference_id: str):
    result = REFERENCE_FILES.get(reference_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reference not found")

    result.analysis_status = "analyzing"
    result.analysis_error = None
    try:
        result.analysis = _analyze_with_gemini(reference_id)
        result.analysis_status = "ready"
    except Exception as exc:
        result.analysis_status = "failed"
        result.analysis_error = str(exc)
        raise HTTPException(status_code=503, detail={
            "message": "Reference analysis is unavailable",
            "reason": result.analysis_error,
        }) from exc

    return result


@router.get("/{reference_id}", response_model=ReferenceUploadResult)
def get_reference(reference_id: str):
    result = REFERENCE_FILES.get(reference_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reference not found")
    return result
