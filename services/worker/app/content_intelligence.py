from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha1
from typing import Any
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .generation import generate_with_failover, parse_generated_json
from .intelligence_store import (
    add_idea,
    add_performance,
    add_watchlist,
    delete_idea,
    get_brand_profile,
    list_ideas,
    list_performance,
    list_watchlist,
    previous_trend_snapshot,
    remove_watchlist,
    save_brand_profile,
    save_trend_snapshot,
)

router = APIRouter(prefix="/intelligence", tags=["content-intelligence"])

GOOGLE_TRENDS_RSS = "https://trends.google.com/trending/rss?geo={geo}"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"


class IntelligenceRequest(BaseModel):
    input: str = Field(min_length=2, max_length=12000)
    context: dict[str, Any] = {}
    language: str = "ar-EG"
    platform: str | None = None
    audience: str | None = None


class WatchTrendRequest(BaseModel):
    geo: str = "EG"
    trend: dict[str, Any]


class InboxRequest(BaseModel):
    text: str = Field(min_length=2, max_length=4000)
    tags: list[str] = []


class BrandProfileRequest(BaseModel):
    profile: dict[str, Any]


class PerformanceRequest(BaseModel):
    title: str
    platform: str | None = None
    views: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    hook: str | None = None
    content_type: str | None = None
    notes: str | None = None


TOOLS: dict[str, dict[str, str]] = {
    "content_gap": {
        "label": "Content Gap Finder",
        "schema": '{"gaps":[{"topic":"","why_gap":"","audience_need":"","content_angle":"","difficulty":"low|medium|high","opportunity_score":0}]}'
    },
    "competitor": {
        "label": "Competitor Idea Analyzer",
        "schema": '{"observed_patterns":[{"pattern":"","evidence":"","why_it_may_work":""}],"hook_patterns":[""],"format_patterns":[""],"content_gaps":[{"gap":"","why_opportunity":"","opportunity_score":0}],"original_ideas":[{"title":"","hook":"","angle":"","format":"","originality_note":""}],"avoid_copying":[""],"recommended_idea":""}'
    },
    "hooks": {
        "label": "Viral Hook Lab",
        "schema": '{"hooks":[{"hook":"","style":"curiosity|shock|question|promise|story","score":0,"reason":""}],"best_hook":""}'
    },
    "series": {
        "label": "Content Series Generator",
        "schema": '{"series_title":"","series_promise":"","episodes":[{"number":1,"title":"","hook":"","core_point":"","cta_to_next":""}]}'
    },
    "repurpose": {
        "label": "Repurpose Engine",
        "schema": '{"shorts":[{"title":"","hook":"","script":"","target_seconds":30}],"posts":[{"platform":"","copy":""}],"quotes":[""]}'
    },
    "evergreen": {
        "label": "Evergreen Radar",
        "schema": '{"ideas":[{"title":"","search_intent":"","why_evergreen":"","angle":"","score":0}]}'
    },
    "audience": {
        "label": "Audience Persona Mode",
        "schema": '{"persona":{"name":"","needs":[""],"pain_points":[""],"language_style":"","best_platforms":[""],"best_formats":[""]},"content_rules":[""]}'
    },
    "calendar": {
        "label": "Content Calendar AI",
        "schema": '{"calendar":[{"day":"","content_type":"trend|evergreen|series|experimental","title":"","goal":"","platform":"","hook":""}],"mix_summary":""}'
    },
    "idea_score": {
        "label": "Idea Score",
        "schema": '{"overall_score":0,"hook_strength":0,"shareability":0,"clarity":0,"saturation_risk":0,"platform_fit":0,"production_ease":0,"strengths":[""],"fixes":[""],"improved_idea":""}'
    },
    "ab_variants": {
        "label": "A/B Version Generator",
        "schema": '{"variants":[{"name":"A","hook":"","opening_visual":"","title":"","difference":"","hypothesis":""}]}'
    },
    "brand_dna": {
        "label": "Brand DNA",
        "schema": '{"voice":"","tone":"","visual_traits":[""],"hook_patterns":[""],"cta_style":"","content_pillars":[""],"do":[""],"avoid":[""]}'
    },
    "comments": {
        "label": "Comment-to-Content",
        "schema": '{"clusters":[{"question_or_need":"","frequency_signal":"","ideas":[{"title":"","hook":"","format":""}]}]}'
    },
    "winning_patterns": {
        "label": "Winning Pattern Memory",
        "schema": '{"patterns":[{"pattern":"","evidence":"","confidence":"low|medium|high","recommendation":""}],"next_tests":[""]}'
    },
    "trend_remix": {
        "label": "Trend Remix",
        "schema": '{"trend_core":"","why_people_care":"","safe_reusable_mechanic":"","ideas":[{"title":"","angle":"","hook":"","format":"","originality_note":""}],"recommended_idea":""}'
    },
    "research": {
        "label": "Research Mode",
        "schema": '{"brief":"","verified_points":[{"claim":"","source_index":1,"confidence":""}],"open_questions":[""],"script_safe_summary":"","warnings":[""]}'
    },
}


def _fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib_request.Request(
        url,
        headers={"User-Agent": "AI-Content-Studio/1.3 (+trend-radar)", "Accept": "application/xml,text/xml,application/json,text/plain,*/*"},
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise RuntimeError(f"Source returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Source network error: {exc.reason}") from exc


def _trend_key(title: str) -> str:
    normalized = re.sub(r"\s+", " ", title.strip().lower())
    return sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _traffic_number(text: str | None) -> int:
    if not text:
        return 0
    cleaned = text.upper().replace(",", "").replace("+", "").strip()
    match = re.search(r"([\d.]+)\s*([KMB]?)", cleaned)
    if not match:
        return 0
    value = float(match.group(1))
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[match.group(2)]
    return int(value * multiplier)


def _age_hours(pub_date: str | None) -> float:
    if not pub_date:
        return 24.0
    try:
        dt = parsedate_to_datetime(pub_date)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600)
    except Exception:
        return 24.0


def _score_trend(traffic: int, age_hours: float, previous: dict[str, Any] | None) -> tuple[float, float, str, float]:
    freshness = max(0.0, 100.0 - min(age_hours, 48.0) / 48.0 * 100.0)
    volume = min(100.0, math.log10(max(traffic, 10)) / 6.0 * 100.0)

    if previous:
        previous_traffic = max(1, int(previous.get("traffic") or 1))
        growth = (traffic - previous_traffic) / previous_traffic
        velocity = min(100.0, max(0.0, 50.0 + growth * 50.0))
    else:
        velocity = min(80.0, 35.0 + freshness * 0.45)

    saturation = min(100.0, (age_hours / 48.0) * 55.0 + (volume / 100.0) * 45.0)
    score = freshness * 0.34 + velocity * 0.34 + volume * 0.22 + (100.0 - saturation) * 0.10
    score = round(min(100.0, max(0.0, score)), 1)

    if age_hours <= 4 and score >= 65:
        lifecycle = "early"
    elif velocity >= 65 and age_hours <= 18:
        lifecycle = "rising"
    elif score >= 60 and age_hours <= 30:
        lifecycle = "strong"
    elif saturation >= 72:
        lifecycle = "saturated"
    else:
        lifecycle = "cooling"
    return score, round(velocity, 1), lifecycle, round(saturation, 1)


def _parse_google_trends(xml_text: str, geo: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    namespaces = {"ht": "https://trends.google.com/trending/rss"}
    items: list[dict[str, Any]] = []
    for node in root.findall("./channel/item"):
        title = (node.findtext("title") or "").strip()
        if not title:
            continue
        traffic_text = node.findtext("ht:approx_traffic", namespaces=namespaces) or ""
        traffic = _traffic_number(traffic_text)
        pub_date = node.findtext("pubDate")
        age = _age_hours(pub_date)
        key = _trend_key(title)
        previous = previous_trend_snapshot(key, geo)
        score, velocity, lifecycle, saturation = _score_trend(traffic, age, previous)

        related = []
        for news in node.findall("ht:news_item", namespaces):
            news_title = news.findtext("ht:news_item_title", namespaces=namespaces)
            news_url = news.findtext("ht:news_item_url", namespaces=namespaces)
            if news_title:
                related.append({"title": news_title, "url": news_url})

        item = {
            "key": key,
            "title": title,
            "geo": geo,
            "source": "google_trends",
            "traffic": traffic,
            "traffic_label": traffic_text,
            "published_at": pub_date,
            "age_hours": round(age, 1),
            "velocity_score": velocity,
            "saturation_score": saturation,
            "score": score,
            "lifecycle": lifecycle,
            "related_news": related[:4],
            "source_url": f"https://trends.google.com/trending?geo={geo}",
        }
        items.append(item)
    return sorted(items, key=lambda item: item["score"], reverse=True)


def refresh_trends(geo: str = "EG", limit: int = 30) -> dict[str, Any]:
    geo = re.sub(r"[^A-Z]", "", geo.upper())[:2] or "EG"
    errors: list[str] = []
    items: list[dict[str, Any]] = []
    try:
        xml_text = _fetch_text(GOOGLE_TRENDS_RSS.format(geo=geo))
        items = _parse_google_trends(xml_text, geo)
    except Exception as exc:
        errors.append(f"google_trends: {str(exc)[:200]}")

    selected = items[:limit]
    for item in selected:
        save_trend_snapshot(item, geo)
    return {
        "geo": geo,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": selected,
        "source_status": {"google_trends": "ok" if items else "unavailable", "tiktok_creative_center": "public_manual_reference"},
        "errors": errors,
        "free_only": True,
    }


def gdelt_research(topic: str, max_records: int = 12) -> list[dict[str, Any]]:
    query = urllib_parse.urlencode({
        "query": topic,
        "mode": "ArtList",
        "maxrecords": max_records,
        "format": "json",
        "sort": "HybridRel",
    })
    try:
        data = json.loads(_fetch_text(f"{GDELT_DOC_API}?{query}", timeout=25))
    except Exception:
        return []
    articles = data.get("articles") or []
    return [
        {
            "title": article.get("title"),
            "url": article.get("url"),
            "domain": article.get("domain"),
            "language": article.get("language"),
            "seendate": article.get("seendate"),
        }
        for article in articles[:max_records]
        if article.get("title") and article.get("url")
    ]


def _tool_prompt(tool: str, request: IntelligenceRequest) -> str:
    spec = TOOLS[tool]
    brand = get_brand_profile().get("profile") or {}
    performance = list_performance(30) if tool == "winning_patterns" else []
    sources = request.context.get("sources") or []

    special_rules = ""
    if tool == "research":
        special_rules = (
            "Use ONLY the supplied SOURCES as evidence for verified_points. "
            "If a claim is not supported by a supplied source, put it in open_questions, not verified_points."
        )
    elif tool == "winning_patterns":
        special_rules = "Infer patterns only from PERFORMANCE DATA. Do not invent metrics that are not present."
    elif tool == "trend_remix":
        special_rules = "Preserve only the reusable trend mechanic or cultural context. Do not copy exact videos, text, logos, characters, or protected creative execution."
    elif tool == "competitor":
        special_rules = (
            "Analyze only the competitor material supplied by the user. Extract structural patterns, gaps and opportunities. "
            "Do not copy exact scripts, wording, characters, logos, story beats or distinctive shots. "
            "Do not invent performance metrics the user did not provide."
        )

    return f"""
You are the Content Intelligence Engine for an Arabic-first social video studio.
Tool: {spec['label']} ({tool})
User input: {request.input}
Language/locale: {request.language}
Platform: {request.platform or 'not specified'}
Audience: {request.audience or 'not specified'}
Context: {json.dumps(request.context, ensure_ascii=False)}
Saved brand DNA: {json.dumps(brand, ensure_ascii=False)}
Performance data: {json.dumps(performance, ensure_ascii=False)}
SOURCES: {json.dumps(sources, ensure_ascii=False)}

{special_rules}
Return JSON only and follow this schema exactly:
{spec['schema']}

Rules:
- Be practical for social content production, not generic marketing advice.
- Prefer original angles and avoid literal copying of reference/trend/competitor content.
- Scores must be 0-100 when present.
- Egyptian Arabic is preferred for user-facing hooks/scripts when language is ar-EG.
""".strip()


def run_tool(tool: str, request: IntelligenceRequest) -> dict[str, Any]:
    if tool not in TOOLS:
        raise HTTPException(status_code=404, detail="Unknown intelligence tool")

    enriched = request.model_copy(deep=True)
    if tool == "research" and not enriched.context.get("sources"):
        enriched.context["sources"] = gdelt_research(enriched.input)
    if tool == "winning_patterns" and not list_performance(1):
        return {
            "provider": "local",
            "content": {"patterns": [], "next_tests": ["أضف نتائج محتوى سابقة أولًا عشان النظام يتعلم من أدائك الحقيقي."]},
            "failover_log": [],
        }

    try:
        text, provider, failover_log = generate_with_failover(_tool_prompt(tool, enriched))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"provider": provider, "content": parse_generated_json(text), "failover_log": failover_log}


@router.get("/tools")
def get_tools():
    return {"tools": [{"id": key, "label": value["label"]} for key, value in TOOLS.items()]}


@router.get("/trends")
def get_trends(
    geo: str = Query(default="EG", min_length=2, max_length=2),
    limit: int = Query(default=30, ge=1, le=50),
):
    return refresh_trends(geo=geo, limit=limit)


@router.post("/trends/refresh")
def post_refresh_trends(
    geo: str = Query(default="EG", min_length=2, max_length=2),
    limit: int = Query(default=30, ge=1, le=50),
):
    return refresh_trends(geo=geo, limit=limit)


@router.get("/watchlist")
def get_watchlist():
    return {"items": list_watchlist()}


@router.post("/watchlist")
def watch_trend(payload: WatchTrendRequest):
    return {"item": add_watchlist(payload.trend, payload.geo)}


@router.delete("/watchlist/{trend_key}")
def unwatch_trend(trend_key: str):
    if not remove_watchlist(trend_key):
        raise HTTPException(status_code=404, detail="Trend is not in watchlist")
    return {"deleted": True, "key": trend_key}


@router.get("/inbox")
def get_inbox(limit: int = Query(default=100, ge=1, le=500)):
    return {"ideas": list_ideas(limit)}


@router.post("/inbox")
def create_inbox_idea(payload: InboxRequest):
    return {"idea": add_idea(payload.text, payload.tags)}


@router.delete("/inbox/{idea_id}")
def remove_inbox_idea(idea_id: str):
    if not delete_idea(idea_id):
        raise HTTPException(status_code=404, detail="Idea not found")
    return {"deleted": True, "id": idea_id}


@router.get("/brand")
def read_brand_profile():
    return get_brand_profile()


@router.put("/brand")
def update_brand_profile(payload: BrandProfileRequest):
    return save_brand_profile(payload.profile)


@router.post("/performance")
def record_performance(payload: PerformanceRequest):
    return {"item": add_performance(payload.model_dump())}


@router.get("/performance")
def get_performance(limit: int = Query(default=100, ge=1, le=500)):
    return {"items": list_performance(limit)}


@router.post("/generate/{tool}")
def generate_intelligence(tool: str, payload: IntelligenceRequest):
    return run_tool(tool, payload)


@router.post("/trend-remix")
def trend_remix(payload: IntelligenceRequest):
    return run_tool("trend_remix", payload)
