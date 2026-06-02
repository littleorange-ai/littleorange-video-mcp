from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from importlib import resources
from typing import Any


@dataclass(frozen=True)
class Operation:
    doc_id: str
    title: str
    summary: str
    folder: str
    method: str
    path: str
    server: str
    parameters: list[dict[str, Any]]
    content_type: str | None
    body_schema: dict[str, Any] | None
    example: Any
    doc_url: str
    tool_name: str


@dataclass(frozen=True)
class Catalog:
    operations: list[Operation]


DOC_ID_TOOL_NAMES = {
    "428191615e0": "create_video_basic",
    "428355733e0": "query_basic",
    "428252369e0": "sora2_t2v",
    "428265584e0": "sora2_i2v",
    "428358839e0": "sora2_query",
    "428234666e0": "veo31_t2v",
    "428338012e0": "veo31_i2v",
    "433482077e0": "veo31_extend",
    "428347989e0": "veo31_query",
    "442690318e0": "vidu_start_end",
    "442560446e0": "vidu_t2v",
    "442587982e0": "vidu_i2v",
    "442695143e0": "vidu_ref",
    "442695142e0": "vidu_ref_subj",
    "442956667e0": "vidu_query",
    "436902105e0": "dreamina_create_video",
    "436902218e0": "dreamina_query_video",
    "463213838e0": "dreamina_aigc_get_asset",
    "463215145e0": "dreamina_aigc_update_asset",
    "463215122e0": "dreamina_aigc_list_assets",
    "463214538e0": "dreamina_aigc_create_asset",
    "463214414e0": "dreamina_aigc_create_asset_group",
    "463213961e0": "dreamina_aigc_get_asset_group",
    "463214320e0": "dreamina_aigc_list_asset_groups",
    "463214374e0": "dreamina_aigc_update_asset_group",
    "463628130e0": "dreamina_live_list_groups",
    "463628131e0": "dreamina_live_get_group",
    "463628134e0": "dreamina_live_update_group",
    "463629028e0": "dreamina_live_list_assets",
    "463629029e0": "dreamina_live_get_asset",
    "463629030e0": "dreamina_live_update_asset",
    "463645855e0": "dreamina_live_create_asset",
    "463612942e0": "dreamina_live_create_h5",
    "463622230e0": "dreamina_live_get_result",
    "463696924e0": "dreamina_delete_asset_group",
    "463697822e0": "dreamina_delete_asset",
}


def _normalize_action_default(value: Any) -> Any:
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def _param_to_schema(param: dict[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(param.get("schema") or {"type": "string"})
    if param.get("description"):
        schema["description"] = param["description"]
    if "example" in param:
        schema["default"] = _normalize_action_default(param["example"])
    return schema


def _sanitize_json_schema(schema: Any) -> Any:
    """Remove Apifox/OpenAPI decoration not accepted by some MCP clients."""
    if isinstance(schema, dict):
        cleaned: dict[str, Any] = {}
        for key, value in schema.items():
            if key.startswith("x-") or key in {"title", "example", "examples"}:
                continue
            cleaned[key] = _sanitize_json_schema(value)
        if cleaned.get("type") == "object" and "properties" not in cleaned:
            cleaned["properties"] = {}
        return cleaned
    if isinstance(schema, list):
        return [_sanitize_json_schema(v) for v in schema]
    return schema


def load_catalog() -> Catalog:
    with resources.files("littleorange_video_mcp").joinpath("api_catalog.json").open("r", encoding="utf-8") as f:
        data = json.load(f)
    operations: list[Operation] = []
    for raw in data["operations"]:
        doc_id = raw["doc_id"]
        tool_name = DOC_ID_TOOL_NAMES.get(doc_id) or re.sub(r"[^a-z0-9]+", "_", raw["summary"].lower()).strip("_")
        operations.append(Operation(tool_name=tool_name, **raw))
    return Catalog(operations=operations)


def operation_by_tool_name(catalog: Catalog, tool_name: str) -> Operation:
    for operation in catalog.operations:
        if operation.tool_name == tool_name:
            return operation
    raise KeyError(f"Unknown tool: {tool_name}")


def _dreamina_create_body_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Loosen Apifox's Dreamina schema to match its own examples and API behavior.

    The upstream OpenAPI marks `role`, `resolution`, `generate_audio`, and
    `return_last_frame` as required even though the official examples omit them.
    More importantly, forcing `role` on `type: text` causes clients to send a
    role in text content, and the API rejects that with "role is not supported
    in text content".
    """
    fixed = copy.deepcopy(schema)
    fixed["required"] = ["model", "content"]
    fixed.setdefault("description", "Dreamina-Seedance 2.0 创建视频请求体；文本 content 不要带 role，媒体 content 才使用 role。")

    content = (fixed.get("properties") or {}).get("content")
    if isinstance(content, dict):
        media_role = {
            "type": "string",
            "description": "仅媒体内容使用：reference_image、first_frame、last_frame、reference_video、reference_audio。文本内容不要传 role。",
            "enum": ["reference_image", "first_frame", "last_frame", "reference_video", "reference_audio"],
        }
        url_object = lambda desc: {
            "type": "object",
            "properties": {"url": {"type": "string", "description": desc}},
            "required": ["url"],
        }
        content["items"] = {
            "type": "object",
            "description": "多模态内容项。type=text 时只传 text，不传 role；图片/视频/音频可传对应 url 与 role。",
            "oneOf": [
                {
                    "properties": {
                        "type": {"const": "text", "description": "文本提示词"},
                        "text": {"type": "string", "description": "文本提示词，中文≤500字，英文≤1000词"},
                    },
                    "required": ["type", "text"],
                    "additionalProperties": False,
                },
                {
                    "properties": {
                        "type": {"const": "image_url", "description": "图片输入"},
                        "image_url": url_object("支持公网URL、Base64、素材ID；格式jpeg/png/webp等，单图小于30MB"),
                        "role": media_role,
                    },
                    "required": ["type", "image_url"],
                    "additionalProperties": False,
                },
                {
                    "properties": {
                        "type": {"const": "video_url", "description": "视频输入"},
                        "video_url": url_object("支持公网URL、素材ID；格式mp4/mov，分辨率480p~1080p，单视频小于50MB"),
                        "role": media_role,
                    },
                    "required": ["type", "video_url"],
                    "additionalProperties": False,
                },
                {
                    "properties": {
                        "type": {"const": "audio_url", "description": "音频输入"},
                        "audio_url": url_object("支持公网URL、Base64、素材ID；格式wav/mp3，单音频小于15MB"),
                        "role": media_role,
                    },
                    "required": ["type", "audio_url"],
                    "additionalProperties": False,
                },
            ],
        }
    return fixed


def build_tool_schema(operation: Operation) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "api_key": {
            "type": "string",
            "description": "可选。LittleOrange 视频 API Key；不传时使用环境变量 LITTLEORANGE_API_KEY。不要在对话中泄露真实密钥。",
        }
    }
    required: list[str] = []

    for param in operation.parameters:
        name = param["name"]
        properties[name] = _param_to_schema(param)
        if param.get("required") and name != "Action":
            required.append(name)

    if operation.body_schema:
        body_schema = _sanitize_json_schema(operation.body_schema)
        if operation.doc_id == "436902105e0":
            body_schema = _dreamina_create_body_schema(body_schema)
        properties["request_body"] = body_schema
        if operation.body_schema.get("required"):
            properties["request_body"].setdefault(
                "description",
                "完整请求体。此 schema 来自 Apifox 文档，保留所有模型参数。",
            )
        required.append("request_body")

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def operation_description(operation: Operation) -> str:
    body_hint = ""
    if operation.body_schema:
        props = ", ".join((operation.body_schema.get("properties") or {}).keys())
        body_hint = f"\n请求体参数: {props}"
    params_hint = ", ".join(p["name"] for p in operation.parameters) or "无"
    return (
        f"{operation.folder} / {operation.summary}\n"
        f"HTTP: {operation.method} {operation.path}\n"
        f"路径/查询参数: {params_hint}{body_hint}\n"
        f"文档: {operation.doc_url}\n"
        "注意：该工具会调用付费/限额 API；仅在用户明确要求生成、查询或管理素材时使用。"
    )
