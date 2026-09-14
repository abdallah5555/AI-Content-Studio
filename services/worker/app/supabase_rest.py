from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


def _raw_service_key() -> str:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()


def _key_is_valid(key: str) -> bool:
    if not key:
        return False
    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        return False
    return key.startswith("sb_secret_") or key.startswith("eyJ")


def configured() -> bool:
    return bool(os.getenv("SUPABASE_URL", "").strip() and _key_is_valid(_raw_service_key()))


def configuration_error() -> str | None:
    if not os.getenv("SUPABASE_URL", "").strip():
        return "SUPABASE_URL is not configured"
    key = _raw_service_key()
    if not key:
        return "SUPABASE_SERVICE_ROLE_KEY is not configured"
    if not _key_is_valid(key):
        return "SUPABASE_SERVICE_ROLE_KEY must be an sb_secret_ key or legacy service_role JWT"
    return None


def _base_url() -> str:
    value = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    if not value:
        raise RuntimeError("SUPABASE_URL is not configured")
    return value


def _service_key() -> str:
    key = _raw_service_key()
    if not _key_is_valid(key):
        raise RuntimeError(configuration_error() or "SUPABASE_SERVICE_ROLE_KEY is invalid")
    return key


def _headers(prefer: str | None = None, *, content_type: str = "application/json") -> dict[str, str]:
    key = _service_key()
    headers = {"apikey": key, "Content-Type": content_type}
    # New sb_secret_* keys are opaque API keys and must not be treated as JWTs.
    # Legacy service_role keys are JWTs and can be sent as Bearer tokens.
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
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


def _encoded_object_path(object_path: str) -> str:
    return "/".join(urllib_parse.quote(part, safe="") for part in object_path.split("/"))


def _object_url(bucket: str, object_path: str) -> str:
    return f"{_base_url()}/storage/v1/object/{urllib_parse.quote(bucket, safe='')}/{_encoded_object_path(object_path)}"


def upload_file(bucket: str, object_path: str, source: str | Path, *, content_type: str = "application/octet-stream") -> str:
    data = Path(source).read_bytes()
    headers = _headers(content_type=content_type)
    headers["x-upsert"] = "true"
    req = urllib_request.Request(_object_url(bucket, object_path), data=data, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(req, timeout=180) as response:
            response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase storage HTTP {exc.code}: {detail[:800]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Supabase storage network error: {exc.reason}") from exc
    return f"{bucket}/{object_path}"


def download_file(bucket: str, object_path: str, destination: str | Path) -> Path:
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib_request.Request(_object_url(bucket, object_path), headers=_headers(), method="GET")
    try:
        with urllib_request.urlopen(req, timeout=180) as response:
            target.write_bytes(response.read())
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase storage HTTP {exc.code}: {detail[:800]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Supabase storage network error: {exc.reason}") from exc
    return target


def create_signed_url(bucket: str, object_path: str, *, expires_in: int = 3600, download_name: str | None = None) -> str:
    path = f"/storage/v1/object/sign/{urllib_parse.quote(bucket, safe='')}/{_encoded_object_path(object_path)}"
    payload: dict[str, Any] = {"expiresIn": max(60, int(expires_in))}
    if download_name:
        payload["download"] = download_name
    result = request_json("POST", path, payload=payload)
    if not isinstance(result, dict):
        raise RuntimeError("Supabase did not return a signed URL")
    signed = result.get("signedURL") or result.get("signedUrl")
    if not signed:
        raise RuntimeError("Supabase signed URL response is missing signedURL")
    signed_text = str(signed)
    return signed_text if signed_text.startswith("http") else f"{_base_url()}{signed_text}"
