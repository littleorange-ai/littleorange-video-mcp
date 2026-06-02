from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

import jsonschema

from .catalog import Operation, build_tool_schema


class LittleOrangeRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedRequest:
    method: str
    url: str
    headers: dict[str, str]
    params: dict[str, Any]
    content_type: str | None
    json_body: dict[str, Any] | None
    form_data: dict[str, Any] | None


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
    return params


def validate_arguments(operation: Operation, arguments: dict[str, Any]) -> None:
    schema = build_tool_schema(operation)
    jsonschema.validate(instance=arguments, schema=schema)


def build_request(operation: Operation, arguments: dict[str, Any]) -> PreparedRequest:
    validate_arguments(operation, arguments)
    path = _substitute_path(operation.path, arguments)
    url = operation.server.rstrip("/") + path
    content_type = operation.content_type
    headers = {"Authorization": f"Bearer {_api_key(arguments)}"}
    params = _query_params(operation, arguments)
    body = arguments.get("request_body")

    json_body = None
    form_data = None
    if body is not None:
        if content_type == "multipart/form-data":
            form_data = dict(body)
        else:
            json_body = dict(body)
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


async def call_operation(operation: Operation, arguments: dict[str, Any]) -> dict[str, Any]:
    # Import lazily so catalog/schema tests can run without optional runtime deps installed.
    import httpx

    request = build_request(operation, arguments)
    timeout = float(os.getenv("LITTLEORANGE_TIMEOUT", "120"))
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
            raise LittleOrangeRequestError(f"HTTP {exc.response.status_code}: {text}") from exc
        except httpx.HTTPError as exc:
            raise LittleOrangeRequestError(f"请求失败: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    return {"text": response.text}


def to_json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
