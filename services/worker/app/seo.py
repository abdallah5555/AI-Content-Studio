from __future__ import annotations

import json
from typing import Any

from .generation import generate_with_failover, parse_generated_json


def _deterministic_attribution(script_result: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    raw = script_result.get("media_attributions") or []
    records = [item for item in raw if isinstance(item, dict)]
    lines: list[str] = []
    for item in records:
        provider = str(item.get("provider") or "Stock media").title()
        creator = str(item.get("creator") or "").strip()
        source_url = str(item.get("source_url") or "").strip()
        label = str(item.get("label") or "").strip()
        text = label or f"Media provided by {provider}"
        if creator:
            text += f" — Creator: {creator}"
        if source_url:
            text += f" — {source_url}"
        lines.append(text)
    return records, "\n".join(lines)


def _contains_arabic(value: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in value)


def _fallback_seo(payload: dict[str, Any], script_content: dict[str, Any]) -> dict[str, Any]:
    title = str(script_content.get("title") or payload.get("idea_prompt") or "Short video").strip()[:120]
    script = str(script_content.get("script") or "").strip()
    description = script[:260] if script else str(payload.get("idea_prompt") or "").strip()[:260]
    platform = str(payload.get("platform") or "social").strip().lower()
    content_type = str(payload.get("content_type") or "content").strip().lower()
    if _contains_arabic(title + description):
        hashtags = ["#محتوى", "#فيديو_قصير"]
        if platform == "tiktok":
            hashtags.append("#تيك_توك")
        elif platform in {"instagram", "reels"}:
            hashtags.append("#ريلز")
        return {
            "title": title,
            "description": description,
            "hashtags": hashtags,
            "keywords": [content_type, platform, str(payload.get("idea_prompt") or "")[:80]],
            "upload_notes": "تم إنشاء بيانات نشر احتياطية محليًا بسبب تعذر مزود الذكاء الاصطناعي الخارجي.",
        }
    return {
        "title": title,
        "description": description,
        "hashtags": ["#ShortVideo", "#Content", f"#{platform.title()}"],
        "keywords": [content_type, platform, str(payload.get("idea_prompt") or "")[:80]],
        "upload_notes": "Local fallback metadata generated because external AI providers were unavailable.",
    }


def generate_seo(payload: dict[str, Any], script_result: dict[str, Any]) -> dict[str, Any]:
    script_content = script_result.get("content") or {}
    prompt = f"""
Create upload-ready SEO metadata for this social video.

Platform: {payload.get('platform')}
Content type: {payload.get('content_type')}
Target duration: {payload.get('duration_seconds')} seconds
User idea: {payload.get('idea_prompt')}
Script data:
{json.dumps(script_content, ensure_ascii=False)}

Return JSON only using this schema:
{{
  "title": "strong platform-appropriate title",
  "description": "concise description with natural keywords",
  "hashtags": ["#tag1", "#tag2"],
  "keywords": ["keyword one", "keyword two"],
  "upload_notes": "short publishing note"
}}

Rules:
- Match the selected platform.
- Avoid misleading clickbait.
- Keep hashtags relevant rather than excessive.
- Write the title and description in the same main language as the script unless the content clearly requires otherwise.
- Do not invent stock-media credits or source links; attribution is attached separately by the application from the exact media selected during production.
""".strip()

    try:
        text, provider, failover_log = generate_with_failover(prompt)
        content = parse_generated_json(text)
    except Exception as exc:
        provider = "local-fallback"
        failover_log = [str(exc)[:500]]
        content = _fallback_seo(payload, script_content)

    records, note = _deterministic_attribution(script_result)
    content["attributions"] = records
    content["attribution_note"] = note
    return {
        "provider": provider,
        "failover_log": failover_log,
        "content": content,
    }
