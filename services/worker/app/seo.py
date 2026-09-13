from __future__ import annotations

import json
from typing import Any

from .generation import generate_with_failover, parse_generated_json


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
  "upload_notes": "short publishing note",
  "attribution_note": "placeholder for stock media/music attribution when required"
}}

Rules:
- Match the selected platform.
- Avoid misleading clickbait.
- Keep hashtags relevant rather than excessive.
- Write the title and description in the same main language as the script unless the content clearly requires otherwise.
""".strip()

    text, provider, failover_log = generate_with_failover(prompt)
    return {
        "provider": provider,
        "failover_log": failover_log,
        "content": parse_generated_json(text),
    }
