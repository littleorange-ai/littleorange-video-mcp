from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import jsonschema

from .catalog import Operation, build_tool_schema
from .config import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT_SECONDS,
    LittleOrangeConfigError,
    get_base_url,
    get_debug_enabled,
    get_log_file,
    get_timeout_seconds,
)


class LittleOrangeRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedRequest:
    method: str
    url: str
    headers: dict[str, str]
    params: dict[str, Any]
    content_type: str | None
    json_body: Any
    form_data: dict[str, Any] | None


def configured_base_url() -> str:
    return get_base_url()


def configured_timeout_seconds() -> float:
    return get_timeout_seconds()


def _api_key(arguments: dict[str, Any]) -> str:
    key = arguments.get("api_key") or os.getenv("LITTLEORANGE_API_KEY")
    if not key:
        raise LittleOrangeRequestError("缺少 API Key：请传入 api_key 或设置 LITTLEORANGE_API_KEY 环境变量。")
    if key.startswith("Bearer "):
        key = key.removeprefix("Bearer ").strip()
    return key


def _substitute_path(path: str, arguments: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in arguments or arguments[name] in (None, ""):
            raise LittleOrangeRequestError(f"缺少路径参数: {name}")
        return str(arguments[name])

    return re.sub(r"\{([^}]+)\}", repl, path)


def _query_params(operation: Operation, arguments: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for param in operation.parameters:
        if param.get("in") != "query":
            continue
        name = param["name"]
        if name in arguments and arguments[name] is not None:
            params[name] = arguments[name]
        elif "example" in param:
            value = param["example"]
            if isinstance(value, list) and len(value) == 1:
                value = value[0]
            params[name] = value
        elif param.get("required"):
            raise LittleOrangeRequestError(f"缺少查询参数: {name}")
    extra_query = arguments.get("query_params")
    if isinstance(extra_query, dict):
        params.update({k: v for k, v in extra_query.items() if v is not None})
    return params


def validate_arguments(operation: Operation, arguments: dict[str, Any]) -> None:
    schema = build_tool_schema(operation)
    jsonschema.validate(instance=arguments, schema=schema)


def _normalize_request_body(operation: Operation, body: Any) -> Any:
    if operation.doc_id != "436902105e0" or not isinstance(body, dict):
        return body
    normalized = dict(body)
    content = normalized.get("content")
    if isinstance(content, list):
        normalized_content: list[Any] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and "role" in item:
                item = dict(item)
                item.pop("role", None)
            normalized_content.append(item)
        normalized["content"] = normalized_content
    return normalized


def _merge_url_query(url: str, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    parsed = urlparse(url)
    if not parsed.query:
        return url, params
    merged = dict(parse_qsl(parsed.query, keep_blank_values=True))
    merged.update(params)
    clean_url = urlunparse(parsed._replace(query=""))
    return clean_url, merged


def build_request(operation: Operation, arguments: dict[str, Any]) -> PreparedRequest:
    normalized_arguments = dict(arguments)
    if operation.body_schema is not None:
        normalized_arguments["request_body"] = _normalize_request_body(operation, arguments.get("request_body"))
    elif normalized_arguments.get("request_body") is None:
        normalized_arguments.pop("request_body", None)
    validate_arguments(operation, normalized_arguments)
    path = _substitute_path(operation.path, normalized_arguments)
    server = get_base_url(normalized_arguments.get("base_url") or operation.server or DEFAULT_BASE_URL)
    url = server + path
    content_type = operation.content_type
    headers = {"Authorization": f"Bearer {_api_key(normalized_arguments)}"}
    custom_headers = normalized_arguments.get("headers")
    if isinstance(custom_headers, dict):
        for key, value in custom_headers.items():
            if key.lower() == "authorization" or value is None:
                continue
            headers[str(key)] = str(value)
    params = _query_params(operation, normalized_arguments)
    url, params = _merge_url_query(url, params)
    body = normalized_arguments.get("request_body")

    json_body = None
    form_data = None
    if body is not None:
        if content_type == "multipart/form-data":
            if not isinstance(body, dict):
                raise LittleOrangeRequestError("multipart/form-data 请求体必须是对象。")
            form_data = dict(body)
        else:
            json_body = body
            headers["Content-Type"] = content_type or "application/json"
    return PreparedRequest(
        method=operation.method,
        url=url,
        headers=headers,
        params=params,
        content_type=content_type,
        json_body=json_body,
        form_data=form_data,
    )


def redact_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.query:
        return url
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    redacted_pairs = []
    for key, value in pairs:
        if any(token in key.lower() for token in ("key", "token", "secret", "auth")):
            redacted_pairs.append((key, "***"))
        else:
            redacted_pairs.append((key, value))
    return urlunparse(parsed._replace(query=urlencode(redacted_pairs)))


def _safe_request_summary(request: PreparedRequest) -> dict[str, Any]:
    return {
        "method": request.method,
        "url": redact_url(request.url),
        "params": request.params,
        "content_type": request.content_type,
    }


def _log_debug(event: dict[str, Any]) -> None:
    if not get_debug_enabled():
        return
    path = get_log_file()
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


async def call_operation(operation: Operation, arguments: dict[str, Any]) -> dict[str, Any]:
    import httpx

    try:
        request = build_request(operation, arguments)
        timeout = configured_timeout_seconds()
    except (LittleOrangeConfigError, jsonschema.ValidationError) as exc:
        raise LittleOrangeRequestError(str(exc)) from exc

    _log_debug({"event": "request.start", **_safe_request_summary(request)})

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if request.form_data is not None:
                response = await client.request(
                    request.method,
                    request.url,
                    headers=request.headers,
                    params=request.params,
                    data=request.form_data,
                )
            else:
                response = await client.request(
                    request.method,
                    request.url,
                    headers=request.headers,
                    params=request.params,
                    json=request.json_body,
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            text = exc.response.text[:4000]
            _log_debug({
                "event": "request.http_error",
                **_safe_request_summary(request),
                "status_code": exc.response.status_code,
                "response_excerpt": text,
            })
            raise LittleOrangeRequestError(
                json.dumps(
                    {
                        "status": "error",
                        "error_type": "http_error",
                        "message": f"HTTP {exc.response.status_code}",
                        "details": {
                            **_safe_request_summary(request),
                            "status_code": exc.response.status_code,
                            "response_excerpt": text,
                        },
                    },
                    ensure_ascii=False,
                )
            ) from exc
        except httpx.HTTPError as exc:
            _log_debug({"event": "request.network_error", **_safe_request_summary(request), "error": str(exc)})
            raise LittleOrangeRequestError(
                json.dumps(
                    {
                        "status": "error",
                        "error_type": "network_error",
                        "message": "请求失败",
                        "details": {**_safe_request_summary(request), "error": str(exc)},
                    },
                    ensure_ascii=False,
                )
            ) from exc

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        result = response.json()
    else:
        result = {"text": response.text}
    _log_debug({"event": "request.success", **_safe_request_summary(request), "response_type": content_type or "text/plain"})
    return result


def to_json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
