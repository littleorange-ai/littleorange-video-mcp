from __future__ import annotations

from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .autopoll import (
    AUTO_POLL_TOOL_NAMES,
    DEFAULT_FIRST_POLL_DELAY_SECONDS,
    DEFAULT_MAX_POLL_ATTEMPTS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    create_tool_for_wait_tool,
    configured_first_poll_delay_seconds,
    configured_max_poll_attempts,
    configured_poll_interval_seconds,
    extract_task_id,
    poll_until_complete,
    query_tool_for_create_tool,
)
from .catalog import build_tool_schema, load_catalog, operation_by_tool_name, operation_description
from .client import DEFAULT_BASE_URL, LittleOrangeRequestError, call_operation, configured_base_url, to_json_text
from .config import LittleOrangeConfigError

SERVER_NAME = "littleorange-video-mcp"

catalog = load_catalog()
app = Server(SERVER_NAME)


def _is_force_refresh_enabled() -> bool:
    """Check if force refresh is enabled via environment variable."""
    import os
    raw = os.getenv("LITTLEORANGE_CATALOG_FORCE_REFRESH", "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _refresh_catalog_if_needed():
    """Reload the Apifox-backed catalog when the configured cache is stale.

    The MCP process can stay alive for hours or days in IDE clients.  Loading the
    catalog only at module import means official Apifox updates never reach the
    tool list until the user restarts the client.  load_catalog() already handles
    cache freshness, network failures, and packaged fallback, so calling it at
    MCP request boundaries keeps tools current without breaking offline startup.

    If LITTLEORANGE_CATALOG_FORCE_REFRESH is set to true, always fetch fresh data
    from Apifox regardless of cache freshness.
    """
    global catalog
    force_refresh = _is_force_refresh_enabled()
    catalog = load_catalog(force_refresh=force_refresh)
    return catalog


def _wait_tool_schema(create_tool_name: str) -> dict[str, Any]:
    schema = build_tool_schema(operation_by_tool_name(catalog, create_tool_name))
    props = dict(schema["properties"])
    props.update(
        {
            "poll_interval_seconds": {
                "type": "number",
                "default": DEFAULT_POLL_INTERVAL_SECONDS,
                "minimum": 1,
                "description": "轮询间隔秒数；未传时使用 LITTLEORANGE_POLL_INTERVAL_SECONDS，默认 5 秒。",
            },
            "max_poll_attempts": {
                "type": "integer",
                "default": DEFAULT_MAX_POLL_ATTEMPTS,
                "minimum": 1,
                "maximum": 720,
                "description": "最大轮询次数；未传时使用 LITTLEORANGE_MAX_POLL_ATTEMPTS，默认 60 次。总等待时间约为 interval * attempts。",
            },
            "first_poll_delay_seconds": {
                "type": "number",
                "default": DEFAULT_FIRST_POLL_DELAY_SECONDS,
                "minimum": 0,
                "description": "首次轮询前等待秒数；未传时使用 LITTLEORANGE_FIRST_POLL_DELAY_SECONDS，默认 2 秒。",
            },
        }
    )
    return {
        "type": "object",
        "properties": props,
        "required": schema.get("required", []),
        "additionalProperties": False,
    }


def _wait_tool_description(wait_name: str, create_tool_name: str) -> str:
    create_op = operation_by_tool_name(catalog, create_tool_name)
    query_tool = query_tool_for_create_tool(create_tool_name)
    return (
        f"创建任务并自动轮询到完成：先调用 {create_tool_name}，再用 {query_tool} 查询。优先用于最终要拿到视频 URL 的场景。\n"
        f"原始接口: {create_op.method} {create_op.path}\n"
        "建议：如果只是启动任务可用 create 工具；如果希望单次调用直接返回最终视频链接，优先使用该 _wait 工具。\n"
        "可调参数：base_url、poll_interval_seconds、max_poll_attempts、first_poll_delay_seconds。\n"
        "完成后返回 video_urls、elapsed_seconds、last_status 等信息。生成会消耗 LittleOrange 付费/限额额度。"
    )


def _error_payload(error_type: str, message: str, details: dict[str, Any] | None = None) -> list[TextContent]:
    return [TextContent(type="text", text=to_json_text({"status": "error", "error_type": error_type, "message": message, "details": details or {}}))]


@app.list_tools()
async def list_tools(_request: Any | None = None) -> list[Tool]:
    current_catalog = _refresh_catalog_if_needed()
    tools: list[Tool] = []
    for operation in current_catalog.operations:
        description = operation_description(operation)
        if operation.tool_name in {"vidu_t2v", "vidu_i2v", "veo31_t2v", "dreamina_create_video"}:
            description += "\n建议：需要直接等待结果时，优先使用对应的 _wait 工具。"
        tools.append(
            Tool(
                name=operation.tool_name,
                description=description,
                inputSchema=build_tool_schema(operation),
            )
        )

    for wait_name in AUTO_POLL_TOOL_NAMES:
        create_tool = create_tool_for_wait_tool(wait_name)
        tools.append(
            Tool(
                name=wait_name,
                description=_wait_tool_description(wait_name, create_tool),
                inputSchema=_wait_tool_schema(create_tool),
            )
        )

    tools.extend(
        [
            Tool(
                name="video_generate_wait",
                description="高层视频生成工具：根据 mode=t2v/i2v 和 provider=vidu/veo31/sora2/dreamina 路由到对应 _wait 工具。适合 Agent 优先调用。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string", "enum": ["vidu", "veo31", "sora2", "dreamina"]},
                        "mode": {"type": "string", "enum": ["t2v", "i2v", "extend"]},
                        "base_url": {"type": "string"},
                        "api_key": {"type": "string"},
                        "model_id": {"type": "string"},
                        "poll_interval_seconds": {"type": "number", "minimum": 1},
                        "max_poll_attempts": {"type": "integer", "minimum": 1, "maximum": 720},
                        "first_poll_delay_seconds": {"type": "number", "minimum": 0},
                        "request_body": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["provider", "mode", "request_body"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="image_to_video_wait",
                description="高层图生视频工具：根据 provider 路由到 sora2_i2v_wait / veo31_i2v_wait / vidu_i2v_wait。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string", "enum": ["vidu", "veo31", "sora2"]},
                        "base_url": {"type": "string"},
                        "api_key": {"type": "string"},
                        "model_id": {"type": "string"},
                        "poll_interval_seconds": {"type": "number", "minimum": 1},
                        "max_poll_attempts": {"type": "integer", "minimum": 1, "maximum": 720},
                        "first_poll_delay_seconds": {"type": "number", "minimum": 0},
                        "request_body": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["provider", "request_body"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="video_extend_wait",
                description="高层视频扩展工具：当前路由到 veo31_extend_wait。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string", "enum": ["veo31"]},
                        "base_url": {"type": "string"},
                        "api_key": {"type": "string"},
                        "model_id": {"type": "string"},
                        "poll_interval_seconds": {"type": "number", "minimum": 1},
                        "max_poll_attempts": {"type": "integer", "minimum": 1, "maximum": 720},
                        "first_poll_delay_seconds": {"type": "number", "minimum": 0},
                        "request_body": {"type": "object", "additionalProperties": True},
                    },
                    "required": ["provider", "request_body"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="video_query",
                description="高层视频任务查询工具：根据 provider 路由到对应 query 工具。适合已有任务 ID 的场景。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string", "enum": ["vidu", "veo31", "sora2", "dreamina"]},
                        "base_url": {"type": "string"},
                        "api_key": {"type": "string"},
                        "model_id": {"type": "string"},
                        "id": {"type": "string"},
                    },
                    "required": ["provider", "id"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="asset_upload",
                description="高层素材上传工具：当前路由到 dreamina_aigc_create_asset。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string"},
                        "api_key": {"type": "string"},
                        "request_body": {"type": "object", "additionalProperties": True},
                        "Action": {"type": "string", "default": "CreateAsset"},
                    },
                    "required": ["request_body"],
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="asset_list",
                description="高层素材列表工具：当前路由到 dreamina_aigc_list_assets。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string"},
                        "api_key": {"type": "string"},
                        "Action": {"type": "string", "default": "ListAssets"},
                        "request_body": {"type": "object", "additionalProperties": True},
                    },
                    "additionalProperties": False,
                },
            ),
            Tool(
                name="littleorange_raw_request",
                description=(
                "原始透传调用工具，用于文档新增但 MCP 尚未封装的接口，或需要传递非标准请求体时使用。"
                "支持 method/path/model_id/id/Action/request_body/api_key/base_url/query_params/headers。默认读取 LITTLEORANGE_BASE_URL，未设置时为 https://vg-api.aig-ai.com。"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "POST"},
                        "base_url": {"type": "string", "default": DEFAULT_BASE_URL},
                        "path": {"type": "string", "description": "例如 /v1/{model_id} 或 /materials"},
                        "model_id": {"type": "string"},
                        "id": {"type": "string"},
                        "Action": {"type": "string"},
                        "query_params": {"type": "object", "additionalProperties": True},
                        "headers": {"type": "object", "additionalProperties": {"type": "string"}},
                        "request_body": {},
                        "api_key": {"type": "string", "description": "可选；不传时使用 LITTLEORANGE_API_KEY。"},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            ),
        ]
    )
    return tools


def _route_wait_tool(provider: str, mode: str) -> str:
    mapping = {
        ("vidu", "t2v"): "vidu_t2v_wait",
        ("vidu", "i2v"): "vidu_i2v_wait",
        ("veo31", "t2v"): "veo31_t2v_wait",
        ("veo31", "i2v"): "veo31_i2v_wait",
        ("veo31", "extend"): "veo31_extend_wait",
        ("sora2", "t2v"): "sora2_t2v_wait",
        ("sora2", "i2v"): "sora2_i2v_wait",
        ("dreamina", "t2v"): "dreamina_create_video_wait",
    }
    try:
        return mapping[(provider, mode)]
    except KeyError as exc:
        raise LittleOrangeRequestError(f"不支持的 provider/mode 组合: {provider}/{mode}") from exc


def _route_query_tool(provider: str) -> str:
    mapping = {
        "vidu": "vidu_query",
        "veo31": "veo31_query",
        "sora2": "sora2_query",
        "dreamina": "dreamina_query_video",
    }
    try:
        return mapping[provider]
    except KeyError as exc:
        raise LittleOrangeRequestError(f"不支持的 provider: {provider}") from exc


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    _refresh_catalog_if_needed()
    try:
        arguments = arguments or {}
        if name == "littleorange_raw_request":
            return await _raw_request(arguments)
        if name == "video_generate_wait":
            routed_name = _route_wait_tool(arguments["provider"], arguments["mode"])
            routed_arguments = dict(arguments)
            routed_arguments.pop("provider", None)
            routed_arguments.pop("mode", None)
            return await _create_and_wait(routed_name, routed_arguments)
        if name == "image_to_video_wait":
            routed_arguments = dict(arguments)
            provider = routed_arguments.pop("provider")
            return await _create_and_wait(_route_wait_tool(provider, "i2v"), routed_arguments)
        if name == "video_extend_wait":
            routed_arguments = dict(arguments)
            routed_arguments.pop("provider", None)
            return await _create_and_wait("veo31_extend_wait", routed_arguments)
        if name == "video_query":
            operation = operation_by_tool_name(catalog, _route_query_tool(arguments["provider"]))
            routed_arguments = dict(arguments)
            routed_arguments.pop("provider", None)
            result = await call_operation(operation, routed_arguments)
            return [TextContent(type="text", text=to_json_text(result))]
        if name == "asset_upload":
            operation = operation_by_tool_name(catalog, "dreamina_aigc_create_asset")
            result = await call_operation(operation, arguments)
            return [TextContent(type="text", text=to_json_text(result))]
        if name == "asset_list":
            operation = operation_by_tool_name(catalog, "dreamina_aigc_list_assets")
            result = await call_operation(operation, arguments)
            return [TextContent(type="text", text=to_json_text(result))]
        if name in AUTO_POLL_TOOL_NAMES:
            return await _create_and_wait(name, arguments)
        operation = operation_by_tool_name(catalog, name)
        result = await call_operation(operation, arguments)
        return [TextContent(type="text", text=to_json_text(result))]
    except LittleOrangeConfigError as exc:
        return _error_payload("validation_error", str(exc))
    except KeyError as exc:
        return _error_payload("unknown_tool", str(exc))
    except LittleOrangeRequestError as exc:
        try:
            payload = to_json_text(__import__("json").loads(str(exc)))
            return [TextContent(type="text", text=payload)]
        except Exception:
            return _error_payload("request_error", str(exc))
    except Exception as exc:
        return _error_payload("unknown_error", str(exc))


async def _create_and_wait(wait_tool_name: str, arguments: dict[str, Any]) -> list[TextContent]:
    create_tool_name = create_tool_for_wait_tool(wait_tool_name)
    query_tool_name = query_tool_for_create_tool(create_tool_name)
    create_op = operation_by_tool_name(catalog, create_tool_name)
    query_op = operation_by_tool_name(catalog, query_tool_name)

    poll_interval = configured_poll_interval_seconds() if "poll_interval_seconds" not in arguments else arguments.pop("poll_interval_seconds")
    max_attempts = configured_max_poll_attempts() if "max_poll_attempts" not in arguments else arguments.pop("max_poll_attempts")
    first_poll_delay = configured_first_poll_delay_seconds() if "first_poll_delay_seconds" not in arguments else arguments.pop("first_poll_delay_seconds")
    create_result = await call_operation(create_op, arguments)
    task_id = extract_task_id(create_result)
    if not task_id:
        return [
            TextContent(
                type="text",
                text=to_json_text(
                    {
                        "status": "cannot_poll",
                        "message": "创建接口返回中没有找到 task_id/id/name，无法自动轮询。",
                        "create_response": create_result,
                    }
                ),
            )
        ]

    query_args = {key: value for key, value in arguments.items() if key in {"base_url", "api_key", "model_id", "headers", "query_params"} and value is not None}
    for param in query_op.parameters:
        name = param["name"]
        if name == "id":
            query_args[name] = task_id
        elif name in arguments and arguments[name] is not None:
            query_args[name] = arguments[name]
    query_args.setdefault("id", task_id)

    async def query_once() -> dict[str, Any]:
        return await call_operation(query_op, query_args)

    result = await poll_until_complete(
        create_result,
        query_once,
        max_attempts=max_attempts,
        interval_seconds=poll_interval,
        first_poll_delay_seconds=first_poll_delay,
    )
    return [TextContent(type="text", text=to_json_text(result))]


async def _raw_request(arguments: dict[str, Any]) -> list[TextContent]:
    from .catalog import Operation
    from .client import call_operation

    path = arguments["path"]
    request_body = arguments.get("request_body")
    op = Operation(
        doc_id="raw",
        title="raw",
        summary="raw request",
        folder="raw",
        method=arguments.get("method", "POST"),
        path=path,
        server=arguments.get("base_url") or configured_base_url(),
        parameters=[
            {"name": "model_id", "in": "path", "required": "{model_id}" in path, "schema": {"type": "string"}},
            {"name": "id", "in": "path", "required": "{id}" in path, "schema": {"type": "string"}},
            {"name": "Action", "in": "query", "required": False, "schema": {"type": "string"}},
        ],
        content_type="application/json" if request_body is not None else None,
        body_schema={} if request_body is not None else None,
        example=None,
        doc_url="https://video-ai.apifox.cn",
        tool_name="littleorange_raw_request",
    )
    call_arguments = {
        key: value
        for key, value in arguments.items()
        if key in {"base_url", "api_key", "model_id", "id", "Action", "request_body", "query_params", "headers"} and value is not None
    }
    result = await call_operation(op, call_arguments)
    return [TextContent(type="text", text=to_json_text(result))]


async def async_main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    import asyncio

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
