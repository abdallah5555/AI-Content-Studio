from __future__ import annotations

import json
import os
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .reference_store import load_references, save_reference
from .supabase_rest import configured as supabase_configured
from .supabase_rest import download_file as supabase_download_file
from .supabase_rest import upload_file as supabase_upload_file

router = APIRouter(prefix="/references", tags=["references"])

UPLOAD_ROOT = Path("tmp/reference_uploads")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
MAX_REFERENCE_BYTES = 100 * 1024 * 1024
ALLOWED_PREFIXES = ("image/", "video/")
REFERENCE_BUCKET = "content-studio-references"


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


class AvatarProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1200)
    persona_type: Literal["self", "creator", "brand_mascot", "character"] = "creator"
    style: str = Field(default="natural", max_length=120)
    default_wardrobe: str = Field(default="", max_length=500)
    speaking_style: str = Field(default="", max_length=500)


REFERENCE_FILES: dict[str, ReferenceUploadResult] = {}
REFERENCE_PATHS: dict[str, Path] = {}
REFERENCE_STORAGE_PATHS: dict[str, str] = {}


def _split_storage_path(value: str) -> tuple[str, str] | None:
    prefix = f"{REFERENCE_BUCKET}/"
    if not value.startswith(prefix):
        return None
    return REFERENCE_BUCKET, value[len(prefix):]


def _restore_local_path(reference_id: str, stored_path: str, name: str) -> Path:
    storage = _split_storage_path(stored_path)
    if not storage:
        return Path(stored_path)
    bucket, object_path = storage
    suffix = Path(name).suffix[:12]
    destination = UPLOAD_ROOT / f"{reference_id}{suffix}"
    if not destination.exists() and supabase_configured():
        try:
            supabase_download_file(bucket, object_path, destination)
        except Exception:
            pass
    REFERENCE_STORAGE_PATHS[reference_id] = stored_path
    return destination


for stored_reference in load_references():
    try:
        restored = ReferenceUploadResult.model_validate(stored_reference["payload"])
    except Exception:
        continue
    REFERENCE_FILES[restored.id] = restored
    REFERENCE_PATHS[restored.id] = _restore_local_path(restored.id, str(stored_reference["path"]), restored.name)


def _persist_reference(reference_id: str) -> None:
    result = REFERENCE_FILES[reference_id]
    stored_path = REFERENCE_STORAGE_PATHS.get(reference_id) or str(REFERENCE_PATHS[reference_id])
    save_reference(reference_id, stored_path, result.model_dump())


def _ensure_reference_local(reference_id: str) -> Path:
    path = REFERENCE_PATHS[reference_id]
    if path.exists():
        return path
    storage_path = REFERENCE_STORAGE_PATHS.get(reference_id)
    storage = _split_storage_path(storage_path or "")
    if storage and supabase_configured():
        bucket, object_path = storage
        return supabase_download_file(bucket, object_path, path)
    return path


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
    path = _ensure_reference_local(reference_id)
    if not path.exists():
        raise RuntimeError("Reference file is missing from worker and durable storage")

    model = os.getenv("GEMINI_VISION_MODEL", "gemini-3.8-flash")
    client = genai.Client(api_key=api_key)
    uploaded = client.files.upload(file=str(path))
    interaction = client.interactions.create(
        model=model,
        input=[
            {"type": "text", "text": _analysis_prompt(result.kind)},
            {"type": result.kind, "uri": uploaded.uri, "mime_type": result.mime_type},
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

    return {"style_summary": raw_text.strip(), "reusable_traits": [], "avoid_copying": [], "generation_guidance": raw_text.strip()}


def _avatar_payload(result: ReferenceUploadResult) -> dict[str, Any] | None:
    analysis = result.analysis or {}
    profile = analysis.get("avatar_profile")
    if not isinstance(profile, dict):
        return None
    return {
        "reference_id": result.id,
        "reference_name": result.name,
        "kind": result.kind,
        "analysis_status": result.analysis_status,
        "profile": profile,
        "visual_identity": {
            "style_summary": analysis.get("style_summary"),
            "character_object_design": analysis.get("character_object_design"),
            "palette": analysis.get("palette"),
            "lighting": analysis.get("lighting"),
            "generation_guidance": analysis.get("generation_guidance"),
        },
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

    if supabase_configured():
        object_path = f"references/{reference_id}{suffix}"
        storage_path = supabase_upload_file(REFERENCE_BUCKET, object_path, destination, content_type=mime_type)
        REFERENCE_STORAGE_PATHS[reference_id] = storage_path

    _persist_reference(reference_id)
    return result


@router.post("/{reference_id}/analyze", response_model=ReferenceUploadResult)
def analyze_reference(reference_id: str):
    result = REFERENCE_FILES.get(reference_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reference not found")

    existing_avatar = (result.analysis or {}).get("avatar_profile") if isinstance(result.analysis, dict) else None
    result.analysis_status = "analyzing"
    result.analysis_error = None
    _persist_reference(reference_id)
    try:
        result.analysis = _analyze_with_gemini(reference_id)
        if existing_avatar:
            result.analysis["avatar_profile"] = existing_avatar
        result.analysis_status = "ready"
    except Exception as exc:
        result.analysis_status = "failed"
        result.analysis_error = str(exc)
        _persist_reference(reference_id)
        raise HTTPException(status_code=503, detail={"message": "Reference analysis is unavailable", "reason": result.analysis_error}) from exc

    _persist_reference(reference_id)
    return result


@router.get("/avatar-library")
def list_avatar_library():
    avatars = []
    for result in REFERENCE_FILES.values():
        payload = _avatar_payload(result)
        if payload:
            avatars.append(payload)
    return {"avatars": avatars}


@router.post("/{reference_id}/avatar-profile")
def save_avatar_profile(reference_id: str, payload: AvatarProfileRequest):
    result = REFERENCE_FILES.get(reference_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reference not found")
    if result.kind != "image":
        raise HTTPException(status_code=400, detail="Avatar profiles currently require an image reference")

    analysis = dict(result.analysis or {})
    analysis["avatar_profile"] = {
        **payload.model_dump(),
        "reference_id": reference_id,
        "identity_anchor": "Keep the same recognizable person/character identity across scenes while allowing new poses, outfits and environments requested by the user.",
    }
    result.analysis = analysis
    _persist_reference(reference_id)
    return _avatar_payload(result)


@router.get("/{reference_id}", response_model=ReferenceUploadResult)
def get_reference(reference_id: str):
    result = REFERENCE_FILES.get(reference_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reference not found")
    return result
