from __future__ import annotations

from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .autopoll import (
    AUTO_POLL_TOOL_NAMES,
    create_tool_for_wait_tool,
    extract_task_id,
    poll_until_complete,
    query_tool_for_create_tool,
    wait_tool_for_create_tool,
)
from .catalog import build_tool_schema, load_catalog, operation_by_tool_name, operation_description
from .client import LittleOrangeRequestError, call_operation, to_json_text

SERVER_NAME = "littleorange-video-mcp"

catalog = load_catalog()
app = Server(SERVER_NAME)


def _wait_tool_schema(create_tool_name: str) -> dict[str, Any]:
    schema = build_tool_schema(operation_by_tool_name(catalog, create_tool_name))
    props = dict(schema["properties"])
    props.update(
        {
            "poll_interval_seconds": {
                "type": "number",
                "default": 5,
                "minimum": 1,
                "description": "轮询间隔秒数，默认 5 秒。",
            },
            "max_poll_attempts": {
                "type": "integer",
                "default": 60,
                "minimum": 1,
                "maximum": 720,
                "description": "最大轮询次数，默认 60 次。总等待时间约为 interval * attempts。",
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
        f"创建任务并自动轮询到完成：先调用 {create_tool_name}，再用 {query_tool} 查询。\n"
        f"原始接口: {create_op.method} {create_op.path}\n"
        "完成后返回 video_urls 数组和完整查询结果。TRAE/客户端如果支持 URL 预览，可直接展示或打开视频链接；"
        "MCP stdio 本身不能强制客户端内嵌播放。"
    )


@app.list_tools()
async def list_tools() -> list[Tool]:
    tools: list[Tool] = []
    for operation in catalog.operations:
        tools.append(
            Tool(
                name=operation.tool_name,
                description=operation_description(operation),
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

    tools.append(
        Tool(
            name="littleorange_raw_request",
            description=(
            "原始透传调用工具，用于文档新增但 MCP 尚未封装的接口，或需要传递非标准请求体时使用。"
            "支持 method/path/model_id/id/Action/request_body/api_key。默认 base_url 为 https://vg-api.aig-ai.com。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "POST"},
                    "base_url": {"type": "string", "default": "https://vg-api.aig-ai.com"},
                    "path": {"type": "string", "description": "例如 /v1/{model_id} 或 /materials"},
                    "model_id": {"type": "string"},
                    "id": {"type": "string"},
                    "Action": {"type": "string"},
                    "request_body": {"type": "object", "additionalProperties": True},
                    "api_key": {"type": "string", "description": "可选；不传时使用 LITTLEORANGE_API_KEY。"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        )
    )
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        arguments = arguments or {}
        if name == "littleorange_raw_request":
            return await _raw_request(arguments)
        if name in AUTO_POLL_TOOL_NAMES:
            return await _create_and_wait(name, arguments)
        operation = operation_by_tool_name(catalog, name)
        result = await call_operation(operation, arguments)
        return [TextContent(type="text", text=to_json_text(result))]
    except (KeyError, LittleOrangeRequestError, Exception) as exc:
        return [TextContent(type="text", text=f"调用失败: {exc}")]


async def _create_and_wait(wait_tool_name: str, arguments: dict[str, Any]) -> list[TextContent]:
    create_tool_name = create_tool_for_wait_tool(wait_tool_name)
    query_tool_name = query_tool_for_create_tool(create_tool_name)
    create_op = operation_by_tool_name(catalog, create_tool_name)
    query_op = operation_by_tool_name(catalog, query_tool_name)

    poll_interval = float(arguments.pop("poll_interval_seconds", 5))
    max_attempts = int(arguments.pop("max_poll_attempts", 60))
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

    query_args = {
        "model_id": arguments.get("model_id"),
        "id": task_id,
    }
    if arguments.get("api_key"):
        query_args["api_key"] = arguments["api_key"]

    async def query_once() -> dict[str, Any]:
        return await call_operation(query_op, query_args)

    result = await poll_until_complete(
        create_result,
        query_once,
        max_attempts=max_attempts,
        interval_seconds=poll_interval,
    )
    return [TextContent(type="text", text=to_json_text(result))]


async def _raw_request(arguments: dict[str, Any]) -> list[TextContent]:
    # Reuse the same request machinery by constructing a minimal Operation.
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
        server=arguments.get("base_url", "https://vg-api.aig-ai.com"),
        parameters=[
            {"name": "model_id", "in": "path", "required": "{model_id}" in path, "schema": {"type": "string"}},
            {"name": "id", "in": "path", "required": "{id}" in path, "schema": {"type": "string"}},
            {"name": "Action", "in": "query", "required": False, "schema": {"type": "string"}},
        ],
        content_type="application/json" if request_body is not None else None,
        body_schema={"type": "object", "additionalProperties": True} if request_body is not None else None,
        example=None,
        doc_url="https://video-ai.apifox.cn",
        tool_name="littleorange_raw_request",
    )
    call_arguments = {
        key: value
        for key, value in arguments.items()
        if key in {"api_key", "model_id", "id", "Action", "request_body"} and value is not None
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
