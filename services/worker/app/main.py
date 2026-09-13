import asyncio
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .providers import router as providers_router
from .reference_analysis import REFERENCE_FILES, router as references_router

app = FastAPI(title="AI Content Studio Worker", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(providers_router)
app.include_router(references_router)


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
    Stage.TTS: "جاري تجهيز التعليق الصوتي",
    Stage.MEDIA: "جاري اختيار المشاهد المناسبة",
    Stage.EDIT: "جاري تركيب الفيديو والمزامنة",
    Stage.EFFECTS: "جاري إضافة الانتقالات والمؤثرات",
    Stage.MUSIC: "جاري تجهيز الموسيقى الخلفية",
    Stage.EXPORT: "جاري تصدير الفيديو النهائي",
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


jobs: dict[str, dict[str, Any]] = {}


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in job.items() if not key.startswith("_")}


def reference_summary(payload: CreateJobRequest) -> str | None:
    if not payload.reference_ids:
        return None

    references = [REFERENCE_FILES[ref_id] for ref_id in payload.reference_ids if ref_id in REFERENCE_FILES]
    if not references:
        return "تم تحديد مراجع بصرية لكن ملفاتها غير متاحة حاليًا."

    types = sorted({ref.kind for ref in references})
    return (
        f"تم ربط {len(references)} مرجع بصري ({' + '.join(types)}). "
        "سيتم استخدامه لفهم الروح البصرية والتكوين والحركة المختارة، ثم تطبيقها على الفكرة الجديدة بدون نسخ المحتوى نفسه."
    )


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

        # Placeholder processing. Real AI/video providers are connected stage-by-stage.
        await asyncio.sleep(1.2)

        job["progress"] = round((index + 1) / len(STAGES) * 100)

        if job["input"]["review_each_stage"] and index < len(STAGES) - 1:
            job["status"] = "waiting_review"
            job["message"] = "المرحلة جاهزة للمراجعة قبل الاستمرار"
            job["_next_stage_index"] = index + 1
            return

    job["status"] = "completed"
    job["progress"] = 100
    job["stage"] = Stage.SEO.value
    job["message"] = "اكتمل خط الإنتاج التجريبي بنجاح"
    job["_next_stage_index"] = len(STAGES)


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version, "jobs": len(jobs), "references": len(REFERENCE_FILES)}


@app.post("/jobs")
async def create_job(payload: CreateJobRequest):
    missing_reference_ids = [ref_id for ref_id in payload.reference_ids if ref_id not in REFERENCE_FILES]
    if missing_reference_ids:
        raise HTTPException(status_code=400, detail={"missing_reference_ids": missing_reference_ids})

    job_id = str(uuid4())
    job = {
        "id": job_id,
        "status": "queued",
        "stage": Stage.IDEA.value,
        "progress": 0,
        "input": payload.model_dump(),
        "message": "تمت إضافة المهمة إلى خط الإنتاج",
        "reference_summary": reference_summary(payload),
        "_next_stage_index": 0,
    }
    jobs[job_id] = job
    asyncio.create_task(run_pipeline(job_id))
    return public_job(job)


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return public_job(job)


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
    asyncio.create_task(run_pipeline(job_id, next_stage_index))
    return public_job(job)
