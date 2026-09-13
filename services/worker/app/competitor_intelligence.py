from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .generation import generate_with_failover, parse_generated_json
from .intelligence_store import get_brand_profile

router = APIRouter(prefix="/intelligence", tags=["content-intelligence"])


class CompetitorRequest(BaseModel):
    input: str = Field(min_length=2, max_length=12000)
    context: dict[str, Any] = {}
    language: str = "ar-EG"
    platform: str | None = None
    audience: str | None = None


@router.post("/generate/competitor")
def analyze_competitor(payload: CompetitorRequest):
    brand = get_brand_profile().get("profile") or {}
    prompt = f"""
You are the Competitor Idea Analyzer inside an Arabic-first social content studio.

The user supplied competitor examples, transcripts, notes, titles, hooks, or a description of a competing account:
{payload.input}

Platform: {payload.platform or 'not specified'}
Audience: {payload.audience or 'not specified'}
Locale: {payload.language}
Saved user Brand DNA: {json.dumps(brand, ensure_ascii=False)}
Extra context: {json.dumps(payload.context, ensure_ascii=False)}

Analyze patterns without copying protected creative execution. Extract repeatable structures only, then find gaps and original opportunities for the user.

Return JSON only with this schema:
{{
  "observed_patterns": [
    {{"pattern":"", "evidence":"", "why_it_may_work":""}}
  ],
  "hook_patterns": [""],
  "format_patterns": [""],
  "content_gaps": [
    {{"gap":"", "why_opportunity":"", "opportunity_score":0}}
  ],
  "original_ideas": [
    {{"title":"", "hook":"", "angle":"", "format":"", "originality_note":""}}
  ],
  "avoid_copying": [""],
  "recommended_idea": ""
}}

Rules:
- Do not reproduce exact scripts, wording, characters, logos, or distinctive shots.
- Do not claim performance metrics unless the user supplied them.
- Prefer ideas that fit the user's saved Brand DNA while filling gaps competitors missed.
- Scores must be 0-100.
- Use Egyptian Arabic for user-facing hooks when locale is ar-EG.
""".strip()

    try:
        text, provider, failover_log = generate_with_failover(prompt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "provider": provider,
        "content": parse_generated_json(text),
        "failover_log": failover_log,
    }
