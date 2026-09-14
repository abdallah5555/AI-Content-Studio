from __future__ import annotations

import json
import os
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from .job_store import recent_idea_context
from .providers import TEXT_PROVIDERS
from .reference_analysis import REFERENCE_FILES


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


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def _gemini_generate(prompt: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed") from exc
    model = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
    client = genai.Client(api_key=api_key)
    interaction = client.interactions.create(model=model, input=prompt)
    text = interaction.output_text or ""
    if not text.strip():
        raise RuntimeError("Gemini returned an empty response")
    return text.strip()


def _groq_generate(prompt: str) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")
    model = os.getenv("GROQ_TEXT_MODEL", "openai/gpt-oss-20b")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are the writing engine for an AI social-video production studio. Return JSON only when requested."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
    }
    data = _post_json(
        "https://api.groq.com/openai/v1/chat/completions",
        {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        payload,
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError("Groq returned an unexpected response") from exc


def _openrouter_generate(prompt: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    model = os.getenv("OPENROUTER_TEXT_MODEL", "openrouter/free")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are the writing engine for an AI social-video production studio. Return JSON only when requested."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
    }
    data = _post_json(
        "https://openrouter.ai/api/v1/chat/completions",
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("PUBLIC_APP_URL", "https://localhost"),
            "X-Title": "AI Content Studio",
        },
        payload,
    )
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError("OpenRouter returned an unexpected response") from exc


PROVIDER_GENERATORS = {
    "gemini": _gemini_generate,
    "groq": _groq_generate,
    "openrouter": _openrouter_generate,
}


def generate_with_failover(prompt: str) -> tuple[str, str, list[str]]:
    errors: list[str] = []
    for provider in sorted(TEXT_PROVIDERS, key=lambda item: item.priority):
        if not os.getenv(provider.env_key, "").strip():
            errors.append(f"{provider.id}: not configured")
            continue
        generator = PROVIDER_GENERATORS[provider.id]
        try:
            return generator(prompt), provider.id, errors
        except Exception as exc:
            errors.append(f"{provider.id}: {str(exc)[:220]}")
    raise RuntimeError("No text provider succeeded. " + " | ".join(errors))


def _reference_context(reference_ids: list[str], preferences: dict[str, bool]) -> str:
    if not reference_ids:
        return "No visual reference is attached. Build the visual concept from the user's idea."
    sections: list[str] = []
    for index, reference_id in enumerate(reference_ids, start=1):
        result = REFERENCE_FILES.get(reference_id)
        if not result:
            continue
        if result.analysis_status == "ready" and result.analysis:
            guidance = result.analysis.get("generation_guidance") or result.analysis.get("style_summary") or ""
            reusable = result.analysis.get("reusable_traits") or []
            avoid = result.analysis.get("avoid_copying") or []
            sections.append(
                f"Reference {index} ({result.kind}):\n"
                f"Visual guidance: {guidance}\n"
                f"Reusable traits: {json.dumps(reusable, ensure_ascii=False)}\n"
                f"Do not copy literally: {json.dumps(avoid, ensure_ascii=False)}"
            )
        else:
            sections.append(f"Reference {index}: uploaded but visual analysis is not ready. Use only the user's written idea.")
    selected = [key for key, value in preferences.items() if value]
    preserve = ", ".join(selected) if selected else "general visual spirit only"
    return (
        "The user explicitly wants a NEW work inspired by observable properties, not a literal copy.\n"
        f"Preserve these selected traits when useful: {preserve}.\n\n" + "\n\n".join(sections)
    )


def build_idea_prompt(payload: dict[str, Any]) -> str:
    reference_context = _reference_context(payload.get("reference_ids", []), payload.get("reference_preferences", {}))
    recent = recent_idea_context(30)
    recent_context = json.dumps(recent, ensure_ascii=False) if recent else "[]"
    return f"""
Create the IDEA stage for a social-media video.

User request: {payload.get('idea_prompt') or 'Generate a fresh idea suitable for the selected content type.'}
Content type: {payload.get('content_type')}
Platform: {payload.get('platform')}
Aspect ratio: {payload.get('aspect_ratio')}
Target duration: {payload.get('duration_seconds')} seconds

RECENT IDEAS / TITLES ALREADY USED:
{recent_context}

REFERENCE CONTEXT:
{reference_context}

Return JSON only with this schema:
{{
  "idea_title": "short working title",
  "core_idea": "one clear original concept",
  "hook_angle": "the strongest opening angle",
  "audience_promise": "what the viewer gets",
  "visual_direction": "how the selected reference traits should be translated to the new idea",
  "originality_note": "how this differs from previous ideas and any reference instead of copying it"
}}

Rules:
- Compare meaning, angle, promise and hook against RECENT IDEAS, not only exact wording.
- If the user's request overlaps an old topic, choose a meaningfully different angle, question, audience promise, structure or visual treatment.
- Do not reject the user's requested topic merely because it appeared before; make the execution semantically distinct.
- Keep the idea practical for production and appropriate for the target duration.
""".strip()


def build_script_prompt(payload: dict[str, Any], idea_result: dict[str, Any]) -> str:
    reference_context = _reference_context(payload.get("reference_ids", []), payload.get("reference_preferences", {}))
    return f"""
Write the SCRIPT stage for a social-media video based on this approved/generated idea:
{json.dumps(idea_result, ensure_ascii=False)}

User request: {payload.get('idea_prompt')}
Content type: {payload.get('content_type')}
Platform: {payload.get('platform')}
Target duration: {payload.get('duration_seconds')} seconds

REFERENCE CONTEXT:
{reference_context}

Return JSON only with this schema:
{{
  "title": "upload-ready title",
  "hook": "opening line for the first seconds",
  "script": "full spoken narration",
  "cta": "short call to action",
  "scene_plan": [
    {{
      "scene": 1,
      "seconds": 4,
      "visual": "what to show, written for the user",
      "caption": "on-screen text",
      "search_query_en": "concise English stock-video search query describing the visual subject and action"
    }}
  ]
}}

Rules:
- Match the requested duration closely.
- Start with a strong hook and keep retention high.
- Make every scene's search_query_en concrete and suitable for Pexels/Pixabay stock-video search.
- Prefer observable subjects and actions over abstract concepts in search_query_en.
- The script must express the NEW idea, while visual direction may reuse only the selected observable traits from the reference.
- Do not copy distinctive text, characters, logos, story beats, or exact shots from the reference.
""".strip()


def parse_generated_json(text: str) -> dict[str, Any]:
    cleaned = _clean_json_text(text)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    return {"raw": text.strip()}


def _contains_arabic(value: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in value)


def _local_idea(payload: dict[str, Any]) -> dict[str, Any]:
    topic = str(payload.get("idea_prompt") or payload.get("content_type") or "موضوع مفيد").strip()
    if _contains_arabic(topic):
        return {
            "idea_title": topic[:90],
            "core_idea": f"تقديم {topic} في صورة نقطة واضحة وسريعة قابلة للتطبيق.",
            "hook_angle": f"إيه أهم حاجة لازم تعرفها عن {topic[:70]}؟",
            "audience_promise": "معلومة مباشرة وسهلة يمكن تطبيقها فورًا.",
            "visual_direction": "لقطات يومية واضحة، حركة بسيطة، وكابشن كبير مناسب للفيديو العمودي.",
            "originality_note": "نسخة احتياطية محلية تُستخدم فقط عند تعذر مزودات الذكاء الاصطناعي الخارجية.",
        }
    return {
        "idea_title": topic[:90],
        "core_idea": f"Explain {topic} as one clear, practical takeaway.",
        "hook_angle": f"What is the one thing you should know about {topic[:70]}?",
        "audience_promise": "A direct takeaway the viewer can use immediately.",
        "visual_direction": "Clear everyday footage, simple motion, and bold vertical captions.",
        "originality_note": "Local resilience fallback used only when external AI providers are unavailable.",
    }


def _local_script(payload: dict[str, Any], idea_result: dict[str, Any]) -> dict[str, Any]:
    topic = str(payload.get("idea_prompt") or idea_result.get("idea_title") or "الموضوع").strip()
    title = str(idea_result.get("idea_title") or topic or "فيديو قصير").strip()
    core = str(idea_result.get("core_idea") or topic).strip()
    hook = str(idea_result.get("hook_angle") or "").strip()
    promise = str(idea_result.get("audience_promise") or "").strip()
    duration = max(15, int(payload.get("duration_seconds") or 15))
    first = max(3, round(duration * 0.27))
    second = max(4, round(duration * 0.40))
    third = max(3, duration - first - second)
    if _contains_arabic(topic + core + hook):
        hook = hook or f"إيه أهم حاجة لازم تعرفها عن {topic[:70]}؟"
        narration = " ".join(part for part in [hook, core, promise, "ابدأ بخطوة صغيرة وواضحة وراقب النتيجة بنفسك."] if part)
        return {
            "title": title[:120],
            "hook": hook,
            "script": narration,
            "cta": "جرّب الفكرة وشارك النتيجة.",
            "scene_plan": [
                {"scene": 1, "seconds": first, "visual": "لقطة لشخص ينتبه للمشكلة أو الفكرة", "caption": hook[:70], "search_query_en": "person thinking reacting indoors vertical video"},
                {"scene": 2, "seconds": second, "visual": "لقطة توضيحية لخطوة عملية مرتبطة بالفكرة", "caption": core[:70], "search_query_en": "hands demonstrating simple everyday action close up vertical"},
                {"scene": 3, "seconds": third, "visual": "لقطة ختامية إيجابية وواضحة", "caption": "جرّبها بنفسك", "search_query_en": "happy person smiling camera lifestyle vertical video"},
            ],
        }
    hook = hook or f"Here is the one thing to know about {topic[:70]}."
    narration = " ".join(part for part in [hook, core, promise, "Start with one simple step and see the result for yourself."] if part)
    return {
        "title": title[:120],
        "hook": hook,
        "script": narration,
        "cta": "Try it and share the result.",
        "scene_plan": [
            {"scene": 1, "seconds": first, "visual": "A person notices the problem or idea", "caption": hook[:70], "search_query_en": "person thinking reacting indoors vertical video"},
            {"scene": 2, "seconds": second, "visual": "A practical action demonstrating the idea", "caption": core[:70], "search_query_en": "hands demonstrating simple everyday action close up vertical"},
            {"scene": 3, "seconds": third, "visual": "Positive closing lifestyle shot", "caption": "Try it yourself", "search_query_en": "happy person smiling camera lifestyle vertical video"},
        ],
    }


def generate_idea(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        text, provider, failover_log = generate_with_failover(build_idea_prompt(payload))
        return {"provider": provider, "failover_log": failover_log, "content": parse_generated_json(text)}
    except Exception as exc:
        return {
            "provider": "local-fallback",
            "failover_log": [str(exc)[:500]],
            "content": _local_idea(payload),
        }


def generate_script(payload: dict[str, Any], idea_result: dict[str, Any]) -> dict[str, Any]:
    try:
        text, provider, failover_log = generate_with_failover(build_script_prompt(payload, idea_result))
        return {"provider": provider, "failover_log": failover_log, "content": parse_generated_json(text)}
    except Exception as exc:
        return {
            "provider": "local-fallback",
            "failover_log": [str(exc)[:500]],
            "content": _local_script(payload, idea_result),
        }
