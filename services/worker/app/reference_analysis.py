from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Literal
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
    analysis_status: Literal["queued", "ready"] = "queued"


REFERENCE_FILES: dict[str, ReferenceUploadResult] = {}


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
    return result


@router.get("/{reference_id}", response_model=ReferenceUploadResult)
def get_reference(reference_id: str):
    result = REFERENCE_FILES.get(reference_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reference not found")
    return result
