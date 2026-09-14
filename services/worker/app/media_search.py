from __future__ import annotations

import json
import os
from typing import Any
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


DEFAULT_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

PEXELS_TARGETS: dict[str, tuple[int, int]] = {
    "9:16": (720, 1280),
    "4:5": (720, 900),
    "1:1": (720, 720),
    "16:9": (1280, 720),
}


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> dict[str, Any]:
    request_headers = {**DEFAULT_HTTP_HEADERS, **(headers or {})}
    req = urllib_request.Request(url, headers=request_headers, method="GET")
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:400]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def _orientation(aspect_ratio: str) -> str:
    if aspect_ratio in {"9:16", "4:5"}:
        return "portrait"
    if aspect_ratio == "1:1":
        return "square"
    return "landscape"


def _best_pexels_file(video_files: list[dict[str, Any]], aspect_ratio: str) -> dict[str, Any] | None:
    if not video_files:
        return None
    portrait = aspect_ratio in {"9:16", "4:5"}
    target_width, target_height = PEXELS_TARGETS.get(aspect_ratio, PEXELS_TARGETS["9:16"])
    target_area = target_width * target_height

    def score(item: dict[str, Any]) -> tuple[int, int, int]:
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        orientation_match = int((height >= width) if portrait else (width >= height))
        render_sized = int(width <= target_width * 1.25 and height <= target_height * 1.25)
        area_distance = -abs((width * height) - target_area)
        return orientation_match, render_sized, area_distance

    candidates = [item for item in video_files if item.get("link")]
    return max(candidates, key=score) if candidates else None


def search_pexels_video(query: str, aspect_ratio: str) -> dict[str, Any]:
    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PEXELS_API_KEY is not configured")
    params = urllib_parse.urlencode({"query": query[:120], "orientation": _orientation(aspect_ratio), "size": "medium", "per_page": 8, "page": 1})
    data = _get_json(f"https://api.pexels.com/v1/videos/search?{params}", headers={"Authorization": api_key})
    videos = data.get("videos") or []
    if not videos:
        raise RuntimeError(f"Pexels returned no video results for: {query}")
    for video in videos:
        selected_file = _best_pexels_file(video.get("video_files") or [], aspect_ratio)
        if not selected_file:
            continue
        user = video.get("user") or {}
        return {
            "provider": "pexels", "media_type": "video", "id": str(video.get("id")), "query": query,
            "preview_url": video.get("image") or "", "download_url": selected_file.get("link"),
            "width": selected_file.get("width"), "height": selected_file.get("height"), "duration": video.get("duration"),
            "page_url": video.get("url"), "creator": user.get("name"), "creator_url": user.get("url"),
            "attribution": "Video provided by Pexels",
        }
    raise RuntimeError(f"Pexels results had no usable files for: {query}")


def _best_pixabay_video(videos: dict[str, Any], aspect_ratio: str) -> tuple[str, dict[str, Any]] | None:
    preferred = ["large", "medium", "small", "tiny"]
    portrait = aspect_ratio in {"9:16", "4:5"}
    candidates: list[tuple[str, dict[str, Any], tuple[int, int]]] = []
    for label in preferred:
        item = videos.get(label)
        if not isinstance(item, dict) or not item.get("url"):
            continue
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        orientation_match = int((height >= width) if portrait else (width >= height))
        candidates.append((label, item, (orientation_match, width * height)))
    if not candidates:
        return None
    label, item, _ = max(candidates, key=lambda row: row[2])
    return label, item


def search_pixabay_video(query: str, aspect_ratio: str) -> dict[str, Any]:
    api_key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PIXABAY_API_KEY is not configured")
    params = urllib_parse.urlencode({"key": api_key, "q": query[:100], "video_type": "all", "safesearch": "true", "order": "popular", "per_page": 10, "page": 1})
    data = _get_json(f"https://pixabay.com/api/videos/?{params}")
    hits = data.get("hits") or []
    if not hits:
        raise RuntimeError(f"Pixabay returned no video results for: {query}")
    for hit in hits:
        best = _best_pixabay_video(hit.get("videos") or {}, aspect_ratio)
        if not best:
            continue
        _, selected = best
        return {
            "provider": "pixabay", "media_type": "video", "id": str(hit.get("id")), "query": query,
            "preview_url": hit.get("picture_id") and f"https://i.vimeocdn.com/video/{hit.get('picture_id')}_640x360.jpg",
            "download_url": selected.get("url"), "width": selected.get("width"), "height": selected.get("height"),
            "duration": hit.get("duration"), "page_url": hit.get("pageURL"), "creator": hit.get("user"),
            "creator_url": None, "attribution": "Video provided by Pixabay",
        }
    raise RuntimeError(f"Pixabay results had no usable files for: {query}")


MEDIA_PROVIDERS = (
    ("pexels", "PEXELS_API_KEY", search_pexels_video),
    ("pixabay", "PIXABAY_API_KEY", search_pixabay_video),
)


def search_video_with_failover(query: str, aspect_ratio: str) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    for provider_id, env_key, searcher in MEDIA_PROVIDERS:
        if not os.getenv(env_key, "").strip():
            errors.append(f"{provider_id}: not configured")
            continue
        try:
            return searcher(query, aspect_ratio), errors
        except Exception as exc:
            errors.append(f"{provider_id}: {str(exc)[:220]}")
    raise RuntimeError("No media provider succeeded. " + " | ".join(errors))


def _attribution_record(media: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": media.get("provider"),
        "media_id": media.get("id"),
        "creator": media.get("creator"),
        "creator_url": media.get("creator_url"),
        "source_url": media.get("page_url"),
        "label": media.get("attribution"),
    }


def select_media_for_script(script_result: dict[str, Any], aspect_ratio: str) -> dict[str, Any]:
    content = script_result.get("content") or {}
    scene_plan = content.get("scene_plan") or []
    if not isinstance(scene_plan, list) or not scene_plan:
        raise RuntimeError("Script has no scene_plan to search media for")

    selections: list[dict[str, Any]] = []
    global_failover: list[str] = []
    attributions: list[dict[str, Any]] = []
    seen_attribution_keys: set[tuple[str, str]] = set()

    for index, scene in enumerate(scene_plan, start=1):
        if not isinstance(scene, dict):
            continue
        query = str(scene.get("search_query_en") or scene.get("visual") or "").strip() or "cinematic social media background"
        media, failover_log = search_video_with_failover(query, aspect_ratio)
        global_failover.extend(f"scene {index}: {item}" for item in failover_log)
        selections.append({
            "scene": scene.get("scene", index), "seconds": scene.get("seconds"), "visual": scene.get("visual"),
            "caption": scene.get("caption"), "search_query": query, "media": media,
        })
        record = _attribution_record(media)
        key = (str(record.get("provider") or ""), str(record.get("media_id") or ""))
        if key not in seen_attribution_keys:
            seen_attribution_keys.add(key)
            attributions.append(record)

    if not selections:
        raise RuntimeError("No usable scenes were found in the script plan")

    script_result["media_attributions"] = attributions
    word_timings = [item for item in (script_result.get("word_timings") or []) if isinstance(item, dict)]

    providers_used = sorted({item["media"]["provider"] for item in selections})
    return {
        "provider": "+".join(providers_used),
        "failover_log": global_failover,
        "content": {
            "scene_count": len(selections),
            "selections": selections,
            "attribution_required": True,
            "attributions": attributions,
            "word_timings": word_timings,
        },
    }
