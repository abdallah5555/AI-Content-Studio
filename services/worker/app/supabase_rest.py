from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


def configured() -> bool:
    return bool(os.getenv("SUPABASE_URL", "").strip() and os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip())


def _base_url() -> str:
    value = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    if not value:
        raise RuntimeError("SUPABASE_URL is not configured")
    return value


def _service_key() -> str:
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured")
    return key


def _headers(prefer: str | None = None, *, content_type: str = "application/json") -> dict[str, str]:
    key = _service_key()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": content_type}
    if prefer:
        headers["Prefer"] = prefer
    return headers


def request_json(method: str, path: str, *, query: dict[str, str] | None = None, payload: Any | None = None, prefer: str | None = None, timeout: int = 30) -> Any:
    url = f"{_base_url()}{path}"
    if query:
        url += "?" + urllib_parse.urlencode(query, safe="(),.*")
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib_request.Request(url, data=body, headers=_headers(prefer), method=method)
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else None
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase HTTP {exc.code}: {detail[:800]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Supabase network error: {exc.reason}") from exc


def select(table: str, *, columns: str = "*", filters: dict[str, str] | None = None, order: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    query: dict[str, str] = {"select": columns}
    if filters:
        query.update(filters)
    if order:
        query["order"] = order
    if limit is not None:
        query["limit"] = str(limit)
    result = request_json("GET", f"/rest/v1/{table}", query=query)
    return result if isinstance(result, list) else []


def insert(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    result = request_json("POST", f"/rest/v1/{table}", payload=payload, prefer="return=representation")
    if isinstance(result, list) and result:
        return result[0]
    return payload


def upsert(table: str, payload: dict[str, Any], *, on_conflict: str | None = None) -> None:
    query = {"on_conflict": on_conflict} if on_conflict else None
    request_json("POST", f"/rest/v1/{table}", query=query, payload=payload, prefer="resolution=merge-duplicates,return=minimal")


def update(table: str, filters: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = request_json("PATCH", f"/rest/v1/{table}", query=filters, payload=payload, prefer="return=representation")
    return result if isinstance(result, list) else []


def delete(table: str, filters: dict[str, str]) -> None:
    request_json("DELETE", f"/rest/v1/{table}", query=filters, prefer="return=minimal")


def upload_file(bucket: str, object_path: str, source: str | Path, *, content_type: str = "application/octet-stream") -> str:
    source_path = Path(source)
    data = source_path.read_bytes()
    encoded_path = "/".join(urllib_parse.quote(part, safe="") for part in object_path.split("/"))
    url = f"{_base_url()}/storage/v1/object/{urllib_parse.quote(bucket, safe='')}/{encoded_path}"
    headers = _headers(content_type=content_type)
    headers["x-upsert"] = "true"
    req = urllib_request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(req, timeout=180) as response:
            response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase storage HTTP {exc.code}: {detail[:800]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Supabase storage network error: {exc.reason}") from exc
    return f"{bucket}/{object_path}"
