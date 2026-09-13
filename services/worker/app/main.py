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


for _feature_router in (providers_router, references_router, tts_router, music_router, intelligence_router):
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


class ReferencePreferences(BaseModel):
    preserve_style: bool = True
    preserve_colors: bool = True
    preserve_composition: bool = False
    preserve_motion: bool = False
    preserve_character_shape: bool = True


class CreateJobRequest(BaseModel):
    platform: str
    aspect_ratio: str
    duration_seconds: int = Field(ge=15, le=300)
    content_type: str
    review_each_stage: bool = False
    idea_prompt: str = Field(default="", max_length=4000)
    reference_mode: Literal["none", "adapt_style_to_new_idea"] = "none"
    reference_ids: list[str] = []
    reference_preferences: ReferencePreferences = ReferencePreferences()
    tts_voice: str = "ar-EG-SalmaNeural"
    tts_rate: str = "+0%"
    music_volume: float = Field(default=0.12, ge=0.0, le=0.5)


class ManualStageEdit(BaseModel):
    content: dict[str, Any]


init_job_store()
jobs: dict[str, dict[str, Any]] = load_jobs()

for restored_job in jobs.values():
    if restored_job.get("status") in {"queued", "running"}:
        restored_job["status"] = "failed"
        restored_job["message"] = "توقفت المهمة بسبب إعادة تشغيل الـWorker. يمكنك إعادة توليد المرحلة الحالية."
        restored_job["error"] = "Worker restarted while this job was in progress"
        save_job(restored_job)


def checkpoint(job: dict[str, Any]) -> None:
    save_job(job)


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in job.items() if not key.startswith("_")}


def reference_summary(payload: CreateJobRequest) -> str | None:
    if not payload.reference_ids:
        return None
    references = [REFERENCE_FILES[ref_id] for ref_id in payload.reference_ids if ref_id in REFERENCE_FILES]
    if not references:
        return "تم تحديد مراجع بصرية لكن ملفاتها غير متاحة حاليًا."
    ready_count = sum(1 for ref in references if ref.analysis_status == "ready")
    types = sorted({ref.kind for ref in references})
    return (
        f"تم ربط {len(references)} مرجع بصري ({' + '.join(types)}), وتم تحليل {ready_count} منها. "
        "سيتم استخدام السمات البصرية القابلة لإعادة الاستخدام فقط، ثم تطبيقها على الفكرة الجديدة بدون نسخ المحتوى نفسه."
    )


def stage_output_for(job: dict[str, Any], stage: Stage) -> dict[str, Any] | None:
    return job.get("outputs", {}).get(stage.value)


def stage_index(stage: Stage) -> int:
    return STAGES.index(stage)


def invalidate_from(job: dict[str, Any], start_index: int) -> None:
    outputs = job.setdefault("outputs", {})
    for stage in STAGES[start_index:]:
        outputs.pop(stage.value, None)


async def execute_stage(job: dict[str, Any], stage: Stage) -> None:
    payload = job["input"]

    if stage == Stage.IDEA:
        result = await asyncio.to_thread(generate_idea, payload)
        job["outputs"][Stage.IDEA.value] = result
        job["stage_output"] = result
        job["active_provider"] = result.get("provider")
        job["provider_failover_log"] = result.get("failover_log", [])
        return

    if stage == Stage.SCRIPT:
        idea_result = stage_output_for(job, Stage.IDEA)
        if not idea_result:
            raise RuntimeError("Script generation requires a completed idea stage")
        result = await asyncio.to_thread(generate_script, payload, idea_result.get("content", {}))
        job["outputs"][Stage.SCRIPT.value] = result
        job["stage_output"] = result
        job["active_provider"] = result.get("provider")
        job["provider_failover_log"] = result.get("failover_log", [])
        return

    if stage == Stage.TTS:
        script_result = stage_output_for(job, Stage.SCRIPT)
        if not script_result:
            raise RuntimeError("TTS generation requires a completed script stage")
        result = await generate_tts(
            script_result,
            voice=payload.get("tts_voice") or None,
            rate=payload.get("tts_rate") or None,
        )
        result["audio_url"] = f"/media/tts/{result['audio_id']}.mp3"
        job["outputs"][Stage.TTS.value] = result
        job["stage_output"] = result
        job["active_provider"] = result.get("provider")
        job["provider_failover_log"] = []
        return

    if stage == Stage.MEDIA:
        script_result = stage_output_for(job, Stage.SCRIPT)
        if not script_result:
            raise RuntimeError("Media selection requires a completed script stage")
        result = await asyncio.to_thread(select_media_for_script, script_result, payload.get("aspect_ratio") or "9:16")
        job["outputs"][Stage.MEDIA.value] = result
        job["stage_output"] = result
        job["active_provider"] = result.get("provider")
        job["provider_failover_log"] = result.get("failover_log", [])
        return

    if stage == Stage.EDIT:
        media_result = stage_output_for(job, Stage.MEDIA)
        tts_result = stage_output_for(job, Stage.TTS)
        if not media_result or not tts_result:
            raise RuntimeError("Edit stage requires completed media and TTS stages")
        result = await asyncio.to_thread(render_montage, media_result, tts_result, payload.get("aspect_ratio") or "9:16")
        job["outputs"][Stage.EDIT.value] = result
        job["stage_output"] = result
        job["active_provider"] = result.get("provider")
        job["provider_failover_log"] = []
        return

    if stage == Stage.EFFECTS:
        edit_result = stage_output_for(job, Stage.EDIT)
        media_result = stage_output_for(job, Stage.MEDIA)
        if not edit_result or not media_result:
            raise RuntimeError("Effects stage requires completed edit and media stages")
        result = await asyncio.to_thread(apply_effects, edit_result, media_result)
        job["outputs"][Stage.EFFECTS.value] = result
        job["stage_output"] = result
        job["active_provider"] = result.get("provider")
        job["provider_failover_log"] = []
        return

    if stage == Stage.MUSIC:
        effects_result = stage_output_for(job, Stage.EFFECTS)
        if not effects_result:
            raise RuntimeError("Music stage requires a completed effects stage")
        result = await asyncio.to_thread(mix_background_music, effects_result, float(payload.get("music_volume") or 0.12))
        job["outputs"][Stage.MUSIC.value] = result
        job["stage_output"] = result
        job["active_provider"] = result.get("provider")
        job["provider_failover_log"] = []
        return

    if stage == Stage.EXPORT:
        music_result = stage_output_for(job, Stage.MUSIC)
        script_result = stage_output_for(job, Stage.SCRIPT)
        if not music_result or not script_result:
            raise RuntimeError("Export stage requires completed music and script stages")
        result = await asyncio.to_thread(export_video, music_result, script_result)
        job["outputs"][Stage.EXPORT.value] = result
        job["stage_output"] = result
        job["active_provider"] = result.get("provider")
        job["provider_failover_log"] = []
        return

    if stage == Stage.SEO:
        script_result = stage_output_for(job, Stage.SCRIPT)
        if not script_result:
            raise RuntimeError("SEO stage requires a completed script stage")
        result = await asyncio.to_thread(generate_seo, payload, script_result)
        job["outputs"][Stage.SEO.value] = result
        job["stage_output"] = result
        job["active_provider"] = result.get("provider")
        job["provider_failover_log"] = result.get("failover_log", [])
        return


async def run_pipeline(job_id: str, start_index: int = 0) -> None:
    job = jobs.get(job_id)
    if not job:
        return
    for index in range(start_index, len(STAGES)):
        stage = STAGES[index]
        job["status"] = "running"
        job["stage"] = stage.value
        job["progress"] = round(index / len(STAGES) * 100)
        job["message"] = STAGE_MESSAGES[stage]
        job["_next_stage_index"] = index
        job["error"] = None
        checkpoint(job)
        try:
            await execute_stage(job, stage)
        except Exception as exc:
            job["status"] = "failed"
            job["message"] = f"فشلت مرحلة {stage.value}"
            job["error"] = str(exc)
            job["_next_stage_index"] = index
            checkpoint(job)
            return
        job["progress"] = round((index + 1) / len(STAGES) * 100)
        checkpoint(job)
        if job["input"]["review_each_stage"] and index < len(STAGES) - 1:
            job["status"] = "waiting_review"
            job["message"] = "المرحلة جاهزة للمراجعة قبل الاستمرار"
            job["_next_stage_index"] = index + 1
            checkpoint(job)
            return
    job["status"] = "completed"
    job["progress"] = 100
    job["stage"] = Stage.SEO.value
    job["message"] = "اكتمل خط الإنتاج بنجاح وأصبح ملف MP4 وبيانات النشر جاهزين"
    job["_next_stage_index"] = len(STAGES)
    checkpoint(job)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": app.version,
        "jobs": len(jobs),
        "references": len(REFERENCE_FILES),
        "ffmpeg": ffmpeg_available(),
        "persistence": "sqlite",
        "content_intelligence": True,
    }


@app.get("/jobs")
def list_jobs(limit: int = Query(default=50, ge=1, le=200)):
    return {"jobs": list_job_summaries(limit)}


@app.post("/jobs")
async def create_job(payload: CreateJobRequest):
    missing_reference_ids = [ref_id for ref_id in payload.reference_ids if ref_id not in REFERENCE_FILES]
    if missing_reference_ids:
        raise HTTPException(status_code=400, detail={"missing_reference_ids": missing_reference_ids})
    if payload.reference_mode == "adapt_style_to_new_idea":
        not_ready = [ref_id for ref_id in payload.reference_ids if REFERENCE_FILES[ref_id].analysis_status != "ready"]
        if not_ready:
            raise HTTPException(
                status_code=409,
                detail={"message": "Reference analysis must finish before generation", "not_ready_reference_ids": not_ready},
            )
    job_id = str(uuid4())
    job = {
        "id": job_id,
        "status": "queued",
        "stage": Stage.IDEA.value,
        "progress": 0,
        "input": payload.model_dump(),
        "message": "تمت إضافة المهمة إلى خط الإنتاج",
        "reference_summary": reference_summary(payload),
        "outputs": {},
        "stage_output": None,
        "active_provider": None,
        "provider_failover_log": [],
        "error": None,
        "_next_stage_index": 0,
    }
    jobs[job_id] = job
    checkpoint(job)
    asyncio.create_task(run_pipeline(job_id))
    return public_job(job)


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return public_job(job)


@app.get("/jobs/{job_id}/outputs")
def get_job_outputs(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job_id,
        "outputs": job.get("outputs", {}),
        "active_provider": job.get("active_provider"),
        "provider_failover_log": job.get("provider_failover_log", []),
    }


@app.delete("/jobs/{job_id}")
def remove_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    jobs.pop(job_id, None)
    delete_stored_job(job_id)
    return {"deleted": True, "id": job_id}


@app.post("/jobs/{job_id}/approve")
async def approve_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "waiting_review":
        raise HTTPException(status_code=409, detail="Job is not waiting for review")
    next_stage_index = job.get("_next_stage_index", 0)
    job["status"] = "queued"
    job["message"] = "تمت الموافقة، جاري استكمال خط الإنتاج"
    checkpoint(job)
    asyncio.create_task(run_pipeline(job_id, next_stage_index))
    return public_job(job)


@app.post("/jobs/{job_id}/stages/{stage_name}/regenerate")
async def regenerate_stage(job_id: str, stage_name: Stage):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "running":
        raise HTTPException(status_code=409, detail="Wait for the active stage to finish before regenerating")
    index = stage_index(stage_name)
    for dependency in STAGES[:index]:
        if not stage_output_for(job, dependency):
            raise HTTPException(status_code=409, detail=f"Missing required previous stage: {dependency.value}")
    invalidate_from(job, index)
    job["status"] = "running"
    job["stage"] = stage_name.value
    job["message"] = f"جاري إعادة توليد مرحلة {stage_name.value}"
    job["error"] = None
    job["progress"] = round(index / len(STAGES) * 100)
    checkpoint(job)
    try:
        await execute_stage(job, stage_name)
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        job["message"] = f"فشلت إعادة توليد مرحلة {stage_name.value}"
        checkpoint(job)
        return public_job(job)
    job["progress"] = round((index + 1) / len(STAGES) * 100)
    job["_next_stage_index"] = index + 1
    if index < len(STAGES) - 1:
        job["status"] = "waiting_review"
        job["message"] = "تمت إعادة التوليد. راجع النتيجة قبل الاستمرار"
    else:
        job["status"] = "completed"
        job["message"] = "تمت إعادة توليد بيانات SEO بنجاح"
    checkpoint(job)
    return public_job(job)


@app.patch("/jobs/{job_id}/stages/{stage_name}")
def edit_stage_output(job_id: str, stage_name: Stage, payload: ManualStageEdit):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "running":
        raise HTTPException(status_code=409, detail="Wait for the active stage to finish before editing")
    if stage_name not in {Stage.IDEA, Stage.SCRIPT, Stage.SEO}:
        raise HTTPException(status_code=400, detail="Manual JSON editing is supported for idea, script and SEO stages")
    index = stage_index(stage_name)
    invalidate_from(job, index + 1)
    result = {"provider": "manual", "failover_log": [], "content": payload.content}
    job["outputs"][stage_name.value] = result
    job["stage_output"] = result
    job["active_provider"] = "manual"
    job["provider_failover_log"] = []
    job["stage"] = stage_name.value
    job["progress"] = round((index + 1) / len(STAGES) * 100)
    job["_next_stage_index"] = index + 1
    job["error"] = None
    if index < len(STAGES) - 1:
        job["status"] = "waiting_review"
        job["message"] = "تم حفظ التعديل اليدوي وإلغاء النواتج اللاحقة القديمة"
    else:
        job["status"] = "completed"
        job["message"] = "تم حفظ تعديل SEO"
    checkpoint(job)
    return public_job(job)
