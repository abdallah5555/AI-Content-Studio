from enum import Enum
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="AI Content Studio Worker", version="0.1.0")

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

class CreateJobRequest(BaseModel):
    platform: str
    aspect_ratio: str
    duration_seconds: int = Field(ge=15, le=300)
    content_type: str
    review_each_stage: bool = False

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/jobs")
def create_job(payload: CreateJobRequest):
    return {
        "status": "queued",
        "stage": Stage.IDEA,
        "progress": 0,
        "input": payload.model_dump(),
        "message": "Pipeline contract ready; provider integrations will be added next."
    }
