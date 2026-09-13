import asyncio
import os
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .content_intelligence import router as intelligence_router
from .effects import EFFECTS_ROOT, apply_effects
from .exporter import EXPORT_ROOT, export_video
from .generation import generate_idea, generate_script
from .job_store import delete_job as delete_stored_job
from .job_store import init_job_store, list_job_summaries, load_jobs, save_job
from .media_search import select_media_for_script
from .music import MUSIC_OUTPUT_ROOT, mix_background_music, router as music_router
from .providers import router as providers_router
from .reference_analysis import REFERENCE_FILES, router as references_router
from .seo import generate_seo
from .tts import OUTPUT_ROOT as TTS_OUTPUT_ROOT
from .tts import generate_tts, router as tts_router
from .video_edit import RENDER_ROOT, ffmpeg_available, render_montage

app = FastAPI(title="AI Content Studio Worker", version="1.3.1")

_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_env_origins = [origin.strip().rstrip("/") for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()]
_public_app_url = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
if _public_app_url:
    _env_origins.append(_public_app_url)
_allowed_origins = list(dict.fromkeys([*_default_origins, *_env_origins]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _attach_router(feature_router) -> None:
    """Register a feature router and guard against route-copy regressions.

    FastAPI normally copies APIRoutes with include_router. Some dependency
    combinations used by CI previously left selected feature routers absent
    from app.routes even though their APIRouter was populated. We first use
    the public API, then attach only route objects whose path+methods are not
    already present. This keeps OpenAPI and request dispatch available without
    duplicating endpoints.
    """
    app.include_router(feature_router)
    existing = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", set()) or set())))
        for route in app.routes
    }
    for route in feature_router.routes:
        signature = (
            getattr(route, "path", ""),
            tuple(sorted(getattr(route, "methods", set()) or set())),
        )
        if signature not in existing:
            app.router.routes.append(route)
            existing.add(signature)


for _feature_router in (
    providers_router,
    references_router,
    tts_router,
    music_router,
    intelligence_router,
):
    _attach_router(_feature_router)

app.mount("/media/tts", StaticFiles(directory=str(TTS_OUTPUT_ROOT)), name="tts-media")
app.mount("/media/renders", StaticFiles(directory=str(RENDER_ROOT)), name="render-media")
app.mount("/media/effects", StaticFiles(directory=str(EFFECTS_ROOT)), name="effects-media")
app.mount("/media/music", StaticFiles(directory=str(MUSIC_OUTPUT_ROOT)), name="music-media")
app.mount("/media/exports", StaticFiles(directory=str(EXPORT_ROOT)), name="export-media")


class Stage(str, Enum):
    IDEA = "idea"
    SCRIPT = "script"
    TTS = "tts"
    MEDIA = "media"
    EDIT = "edit"
    EFFECTS = "effects"
    MUSIC = "music"
    EXPORT = "export"
    SEO = "seo"


STAGES = list(Stage)
STAGE_MESSAGES = {
    Stage.IDEA: "جاري توليد فكرة جديدة وغير مكررة",
    Stage.SCRIPT: "جاري كتابة السكربت والخطاف",
    Stage.TTS: "جاري تحويل السكربت إلى تعليق صوتي",
    Stage.MEDIA: "جاري البحث عن أفضل المشاهد المناسبة",
    Stage.EDIT: "جاري تنزيل المشاهد وتركيب الفيديو مع الصوت",
    Stage.EFFECTS: "جاري إضافة الكابشن والمؤثرات البصرية",
    Stage.MUSIC: "جاري إضافة موسيقى خلفية مناسبة إن توفرت",
    Stage.EXPORT: "جاري تجهيز ملف MP4 النهائي",
    Stage.SEO: "جاري تجهيز العنوان والوصف والكلمات المفتاحية",
}

PROGRESS = {
    Stage.IDEA: 8,
    Stage.SCRIPT: 18,
    Stage.TTS: 32,
    Stage.MEDIA: 45,
    Stage.EDIT: 60,
    Stage.EFFECTS: 72,
    Stage.MUSIC: 82,
    Stage.EXPORT: 92,
    Stage.SEO: 98,
}


class ReferencePreferences(BaseModel):
    preserve_style: bool = True
    preserve_colors: bool = True
    preserve_composition: bool = False
    preserve_motion: bool = False
    preserve_character_shape: bool = True


class CreateJobRequest(BaseModel):
    platform: Literal["tiktok", "instagram", "facebook", "youtube", "x"]
    aspect_ratio: Literal["9:16", "1:1", "4:5", "16:9"]
    duration_seconds: int = Field(ge=15, le=300)
    content_type: str = Field(min_length=2, max_length=100)
    review_each_stage: bool = False
    idea_prompt: str = Field(min_length=2, max_length=4000)
    reference_mode: Literal["none", "adapt_style_to_new_idea"] = "none"
    reference_ids: list[str] = []
    reference_preferences: ReferencePreferences = ReferencePreferences()
    tts_voice: str | None = None
    tts_rate: str = "+0%"
    music_volume: float = Field(default=0.12, ge=0.0, le=0.5)


class ManualStageEditRequest(BaseModel):
    content: dict[str, Any]


JOBS: dict[str, dict[str, Any]] = load_jobs()
for _job in JOBS.values():
    if _job.get("status") in {"queued", "running"}:
        _job["status"] = "failed"
        _job["error"] = "Worker restarted while this job was running. Regenerate the last stage to continue."
        _job["message"] = "تمت مقاطعة المهمة بسبب إعادة تشغيل الـWorker"
        save_job(_job)


EDITABLE_STAGES = {Stage.IDEA, Stage.SCRIPT, Stage.SEO}


def _safe_public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job["id"],
        "status": job["status"],
        "stage": job["stage"],
        "progress": job["progress"],
        "message": job.get("message", ""),
        "input": job["input"],
        "reference_summary": job.get("reference_summary"),
        "outputs": job.get("outputs", {}),
        "stage_output": job.get("outputs", {}).get(job["stage"]),
        "active_provider": job.get("active_provider"),
        "provider_failover_log": job.get("provider_failover_log", []),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


def _persist(job: dict[str, Any]) -> None:
    save_job(job)


def _set_stage(job: dict[str, Any], stage: Stage, message: str | None = None) -> None:
    job["stage"] = stage.value
    job["progress"] = PROGRESS[stage]
    job["message"] = message or STAGE_MESSAGES[stage]
    job["status"] = "running"
    job["error"] = None
    _persist(job)


def _capture_result(job: dict[str, Any], stage: Stage, result: dict[str, Any]) -> None:
    job.setdefault("outputs", {})[stage.value] = result
    provider = result.get("provider")
    if provider:
        job["active_provider"] = provider
    failover_log = result.get("failover_log") or []
    if failover_log:
        job.setdefault("provider_failover_log", []).extend(failover_log)
    _persist(job)


def _review_if_needed(job: dict[str, Any], stage: Stage) -> bool:
    if job["input"].get("review_each_stage"):
        job["status"] = "waiting_review"
        job["message"] = f"بانتظار مراجعة مرحلة {stage.value}"
        _persist(job)
        return True
    return False


def _selected_reference_context(job: dict[str, Any]) -> str | None:
    if job["input"].get("reference_mode") != "adapt_style_to_new_idea":
        return None
    reference_ids = job["input"].get("reference_ids") or []
    if not reference_ids:
        return None
    preferences = job["input"].get("reference_preferences") or {}
    chunks: list[str] = []
    for ref_id in reference_ids:
        reference = REFERENCE_FILES.get(ref_id)
        if not reference or reference.analysis_status != "ready" or not reference.analysis:
            continue
        analysis = reference.analysis
        selected: list[str] = []
        if preferences.get("preserve_style", True):
            selected.extend(filter(None, [analysis.style_summary, analysis.texture_materials, analysis.lighting]))
        if preferences.get("preserve_colors", True) and analysis.palette:
            selected.append(f"Palette: {', '.join(analysis.palette)}")
        if preferences.get("preserve_composition") and analysis.composition:
            selected.append(f"Composition: {analysis.composition}")
        if preferences.get("preserve_motion"):
            selected.extend(filter(None, [analysis.motion, analysis.editing_rhythm]))
        if preferences.get("preserve_character_shape", True) and analysis.character_object_design:
            selected.append(f"Character/object design: {analysis.character_object_design}")
        if analysis.reusable_traits:
            selected.append("Reusable traits: " + "; ".join(analysis.reusable_traits))
        if analysis.avoid_copying:
            selected.append("Avoid copying: " + "; ".join(analysis.avoid_copying))
        if analysis.generation_guidance:
            selected.append("Generation guidance: " + analysis.generation_guidance)
        if selected:
            chunks.append(f"Reference {reference.name}: " + " | ".join(selected))
    return "\n".join(chunks) or None


async def _execute_stage(job: dict[str, Any], stage: Stage) -> None:
    _set_stage(job, stage)
    payload = job["input"]

    if stage == Stage.IDEA:
        result = generate_idea(payload["idea_prompt"], _selected_reference_context(job))
    elif stage == Stage.SCRIPT:
        idea = job["outputs"][Stage.IDEA.value]
        result = generate_script(
            idea,
            duration_seconds=payload["duration_seconds"],
            content_type=payload["content_type"],
            platform=payload["platform"],
            reference_context=_selected_reference_context(job),
        )
    elif stage == Stage.TTS:
        script = job["outputs"][Stage.SCRIPT.value]
        result = await generate_tts(script, voice=payload.get("tts_voice"), rate=payload.get("tts_rate", "+0%"))
    elif stage == Stage.MEDIA:
        script = job["outputs"][Stage.SCRIPT.value]
        result = select_media_for_script(script, payload["aspect_ratio"])
    elif stage == Stage.EDIT:
        result = render_montage(
            job["outputs"][Stage.MEDIA.value],
            job["outputs"][Stage.TTS.value],
            aspect_ratio=payload["aspect_ratio"],
        )
    elif stage == Stage.EFFECTS:
        result = apply_effects(job["outputs"][Stage.EDIT.value], job["outputs"][Stage.SCRIPT.value])
    elif stage == Stage.MUSIC:
        result = mix_background_music(job["outputs"][Stage.EFFECTS.value], volume=payload.get("music_volume", 0.12))
    elif stage == Stage.EXPORT:
        title = (
            job.get("outputs", {}).get(Stage.IDEA.value, {}).get("content", {}).get("title")
            or payload["idea_prompt"]
            or "ai-content-studio"
        )
        result = export_video(job["outputs"][Stage.MUSIC.value], title)
    elif stage == Stage.SEO:
        result = generate_seo(
            idea_result=job["outputs"][Stage.IDEA.value],
            script_result=job["outputs"][Stage.SCRIPT.value],
            platform=payload["platform"],
            content_type=payload["content_type"],
        )
    else:
        raise RuntimeError(f"Unsupported stage: {stage.value}")

    _capture_result(job, stage, result)


async def run_pipeline(job_id: str, start_index: int = 0) -> None:
    job = JOBS[job_id]
    try:
        for index in range(start_index, len(STAGES)):
            stage = STAGES[index]
            await _execute_stage(job, stage)
            if _review_if_needed(job, stage) and stage != Stage.SEO:
                return

        job["status"] = "completed"
        job["progress"] = 100
        job["message"] = "تم تجهيز الفيديو النهائي وبيانات النشر"
        _persist(job)
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        job["message"] = "فشل تنفيذ المرحلة الحالية"
        _persist(job)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": app.version,
        "ffmpeg": ffmpeg_available(),
        "persistence": "sqlite",
        "jobs": len(JOBS),
    }


@app.post("/jobs")
async def create_job(request: CreateJobRequest):
    reference_ids = request.reference_ids if request.reference_mode == "adapt_style_to_new_idea" else []
    missing = [ref_id for ref_id in reference_ids if ref_id not in REFERENCE_FILES]
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown reference IDs: {', '.join(missing)}")

    job_id = str(uuid4())
    job = {
        "id": job_id,
        "status": "queued",
        "stage": Stage.IDEA.value,
        "progress": 0,
        "message": "تمت إضافة المهمة إلى خط الإنتاج",
        "input": request.model_dump(),
        "reference_summary": None,
        "outputs": {},
        "active_provider": None,
        "provider_failover_log": [],
        "error": None,
    }
    JOBS[job_id] = job
    _persist(job)
    asyncio.create_task(run_pipeline(job_id))
    return _safe_public_job(job)


@app.get("/jobs")
def list_jobs(limit: int = Query(default=50, ge=1, le=200)):
    return {"jobs": list_job_summaries(limit)}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _safe_public_job(job)


@app.get("/jobs/{job_id}/outputs")
def get_outputs(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.get("outputs", {})


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    JOBS.pop(job_id, None)
    deleted = delete_stored_job(job_id)
    return {"deleted": deleted, "id": job_id}


@app.post("/jobs/{job_id}/approve")
async def approve_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "waiting_review":
        raise HTTPException(status_code=409, detail="Job is not waiting for review")

    current = Stage(job["stage"])
    if current == Stage.SEO:
        job["status"] = "completed"
        job["progress"] = 100
        job["message"] = "تم تجهيز الفيديو النهائي وبيانات النشر"
        _persist(job)
        return _safe_public_job(job)

    next_index = STAGES.index(current) + 1
    asyncio.create_task(run_pipeline(job_id, start_index=next_index))
    return _safe_public_job(job)


@app.post("/jobs/{job_id}/stages/{stage_name}/regenerate")
async def regenerate_stage(job_id: str, stage_name: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        stage = Stage(stage_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unknown stage") from exc

    current = Stage(job["stage"])
    if stage != current:
        raise HTTPException(status_code=409, detail="Only the current stage can be regenerated")

    current_index = STAGES.index(stage)
    for downstream in STAGES[current_index:]:
        job.get("outputs", {}).pop(downstream.value, None)
    _persist(job)
    asyncio.create_task(run_pipeline(job_id, start_index=current_index))
    return _safe_public_job(job)


@app.patch("/jobs/{job_id}/stages/{stage_name}")
def edit_stage(job_id: str, stage_name: str, request: ManualStageEditRequest):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        stage = Stage(stage_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unknown stage") from exc

    if stage not in EDITABLE_STAGES:
        raise HTTPException(status_code=422, detail="This stage does not support manual JSON editing")
    if Stage(job["stage"]) != stage:
        raise HTTPException(status_code=409, detail="Only the current stage can be edited")

    job.setdefault("outputs", {})[stage.value] = {
        "provider": "manual",
        "content": request.content,
        "failover_log": [],
    }
    current_index = STAGES.index(stage)
    for downstream in STAGES[current_index + 1:]:
        job.get("outputs", {}).pop(downstream.value, None)
    job["status"] = "waiting_review" if job["input"].get("review_each_stage") else "running"
    job["message"] = f"تم تعديل مرحلة {stage.value} يدويًا"
    _persist(job)
    return _safe_public_job(job)
