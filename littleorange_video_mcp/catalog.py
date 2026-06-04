from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - dependency is declared in pyproject
    yaml = None

APIFOX_DOCS_BASE_URL = "https://video-ai.apifox.cn"
APIFOX_LLMS_URL = f"{APIFOX_DOCS_BASE_URL}/llms.txt"
CATALOG_CACHE_VERSION = 1
DEFAULT_CATALOG_REFRESH_SECONDS = 60 * 60
HTTP_TIMEOUT_SECONDS = 20
HTTP_USER_AGENT = "littleorange-video-mcp/catalog-refresh"


def _log_catalog_event(message: str, **kwargs) -> None:
    """Log catalog-related events for debugging purposes."""
    log_path = os.getenv("LITTLEORANGE_CATALOG_LOG_FILE")
    if not log_path:
        return
    try:
        import json
        log_entry = {
            "timestamp": time.time(),
            "message": message,
            **kwargs
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


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

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


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


def _catalog_cache_path() -> Path:
    raw = os.getenv("LITTLEORANGE_CATALOG_CACHE_FILE")
    if raw:
        return Path(raw).expanduser()
    cache_home = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache"))
    return cache_home / "littleorange-video-mcp" / "api_catalog.json"


def _catalog_auto_update_enabled() -> bool:
    raw = os.getenv("LITTLEORANGE_CATALOG_AUTO_UPDATE", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _catalog_refresh_seconds() -> int:
    raw = os.getenv("LITTLEORANGE_CATALOG_REFRESH_SECONDS")
    if raw is None or raw.strip() == "":
        return DEFAULT_CATALOG_REFRESH_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_CATALOG_REFRESH_SECONDS
    return max(0, value)


def _load_packaged_catalog_data() -> dict[str, Any]:
    with resources.files("littleorange_video_mcp").joinpath("api_catalog.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_cached_catalog_data() -> dict[str, Any] | None:
    path = _catalog_cache_path()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("operations"), list):
        return None
    return data


def _cache_is_fresh(data: dict[str, Any]) -> bool:
    refresh_seconds = _catalog_refresh_seconds()
    if refresh_seconds == 0:
        return False
    generated_at = data.get("generated_at")
    if not isinstance(generated_at, (int, float)):
        return False
    return time.time() - float(generated_at) < refresh_seconds


def _write_catalog_cache(data: dict[str, Any]) -> None:
    path = _catalog_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)


def _http_get_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", "replace")


def _normalize_doc_url(url: str) -> str | None:
    """Return a canonical Apifox markdown URL, or None for non-API/doc links."""
    absolute = urljoin(APIFOX_DOCS_BASE_URL, url.strip())
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != urlparse(APIFOX_DOCS_BASE_URL).netloc:
        return None
    if not parsed.path.endswith(".md"):
        return None
    # Strip fragments/query strings so the same doc is only fetched once.
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _discover_api_doc_urls(llms_text: str) -> list[str]:
    """Discover every Apifox markdown doc listed under the API Docs section.

    Official Apifox llms.txt currently separates guide pages under "## Docs" and
    callable API pages under "## API Docs".  Keep only the API section, but do not
    assume document IDs end in a specific suffix beyond ".md"; Apifox IDs can
    change format over time (for example e0/f0/m0 pages exist in the docs list).
    """
    if "## API Docs" in llms_text:
        llms_text = llms_text.split("## API Docs", 1)[1]
        next_section = re.search(r"\n##\s+", llms_text)
        if next_section:
            llms_text = llms_text[: next_section.start()]
    raw_urls = re.findall(r"https?://video-ai\.apifox\.cn/[^\s)\]]+\.md(?:[?#][^\s)\]]*)?|/[0-9A-Za-z_-]+\.md(?:[?#][^\s)\]]*)?", llms_text)
    seen: set[str] = set()
    result: list[str] = []
    for raw_url in raw_urls:
        url = _normalize_doc_url(raw_url)
        if url and url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _extract_first_yaml_block(markdown: str, doc_url: str) -> dict[str, Any] | None:
    if yaml is None:
        raise RuntimeError("PyYAML is required to refresh the Apifox OpenAPI catalog")
    match = re.search(r"```ya?ml\s*(.*?)```", markdown, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    data = yaml.safe_load(match.group(1))
    return data if isinstance(data, dict) else None


def _request_body(operation: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None, Any]:
    request_body = operation.get("requestBody") or {}
    content = request_body.get("content") or {}
    if not isinstance(content, dict) or not content:
        return None, None, None
    preferred_types = ["application/json", "multipart/form-data", *content.keys()]
    for content_type in preferred_types:
        media = content.get(content_type)
        if isinstance(media, dict):
            schema = media.get("schema")
            example = media.get("example")
            if example is None:
                examples = media.get("examples")
                if isinstance(examples, dict) and examples:
                    first = next(iter(examples.values()))
                    if isinstance(first, dict):
                        example = first.get("value")
            return content_type, copy.deepcopy(schema) if isinstance(schema, dict) else None, example
    return None, None, None


def _server_url(spec: dict[str, Any]) -> str:
    servers = spec.get("servers")
    if isinstance(servers, list) and servers:
        first = servers[0]
        if isinstance(first, dict) and isinstance(first.get("url"), str):
            return first["url"].rstrip("/")
    return "https://vg-api.aig-ai.com"


def _stable_generated_tool_name(raw: dict[str, Any], used: set[str]) -> str:
    doc_id = raw["doc_id"]
    mapped = DOC_ID_TOOL_NAMES.get(doc_id)
    if mapped:
        used.add(mapped)
        return mapped

    source = "_".join(filter(None, [raw.get("folder", ""), raw.get("summary", "")])).lower()
    name = re.sub(r"[^a-z0-9]+", "_", source).strip("_")
    if not name or len(name) > 52:
        name = "api_" + doc_id.replace("-", "_")
    name = name[:58].strip("_") or "api"
    base = name
    suffix = 2
    while name in used:
        tail = f"_{suffix}"
        name = f"{base[:60 - len(tail)]}{tail}"
        suffix += 1
    used.add(name)
    return name


def _operation_from_spec(doc_url: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    doc_id = doc_url.rsplit("/", 1)[-1].removesuffix(".md")
    server = _server_url(spec)
    operations: list[dict[str, Any]] = []
    paths = spec.get("paths") or {}
    if not isinstance(paths, dict):
        return operations
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            method_lower = str(method).lower()
            if method_lower not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            parameters = []
            for param in operation.get("parameters") or []:
                if not isinstance(param, dict):
                    continue
                if param.get("in") == "header" and str(param.get("name", "")).lower() == "authorization":
                    continue
                parameters.append(copy.deepcopy(param))
            content_type, body_schema, example = _request_body(operation)
            folder = operation.get("x-apifox-folder") or "/".join(operation.get("tags") or [])
            method_upper = method_lower.upper()
            summary = operation.get("summary") or operation.get("operationId") or f"{method_upper} {path}"
            operations.append(
                {
                    "doc_id": doc_id,
                    "title": summary,
                    "summary": summary,
                    "folder": folder or "",
                    "method": method_upper,
                    "path": path,
                    "server": server,
                    "parameters": parameters,
                    "content_type": content_type,
                    "body_schema": body_schema,
                    "example": example,
                    "doc_url": doc_url,
                }
            )
    return operations


def refresh_catalog_from_apifox() -> dict[str, Any]:
    """Fetch Apifox markdown OpenAPI docs and return a generated catalog."""
    llms_text = _http_get_text(APIFOX_LLMS_URL)
    doc_urls = _discover_api_doc_urls(llms_text)
    if not doc_urls:
        raise RuntimeError("No API docs found in Apifox llms.txt")

    operations: list[dict[str, Any]] = []

    def fetch_operations(doc_url: str) -> list[dict[str, Any]]:
        markdown = _http_get_text(doc_url)
        spec = _extract_first_yaml_block(markdown, doc_url)
        if spec is None:
            return []
        return _operation_from_spec(doc_url, spec)

    with ThreadPoolExecutor(max_workers=min(8, len(doc_urls))) as executor:
        future_map = {executor.submit(fetch_operations, doc_url): doc_url for doc_url in doc_urls}
        for future in as_completed(future_map):
            operations.extend(future.result())

    operations.sort(key=lambda item: doc_urls.index(item["doc_url"]))

    if not operations:
        raise RuntimeError("No operations generated from Apifox docs")

    used: set[str] = set()
    for raw in operations:
        raw["tool_name"] = _stable_generated_tool_name(raw, used)

    digest = hashlib.sha256(json.dumps(operations, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "cache_version": CATALOG_CACHE_VERSION,
        "source": APIFOX_LLMS_URL,
        "generated_at": time.time(),
        "sha256": digest,
        "operations": operations,
    }


def _ensure_tool_names(data: dict[str, Any]) -> dict[str, Any]:
    operations = data.get("operations") or []
    used: set[str] = set()
    changed = False
    for raw in operations:
        if not isinstance(raw, dict):
            continue
        tool_name = raw.get("tool_name")
        if isinstance(tool_name, str) and tool_name and tool_name not in used:
            used.add(tool_name)
            continue
        raw["tool_name"] = _stable_generated_tool_name(raw, used)
        changed = True
    if changed:
        data = dict(data)
        data["operations"] = operations
    return data


def load_catalog_data(*, refresh: bool | None = None, force_refresh: bool = False) -> dict[str, Any]:
    """Load catalog, refreshing from Apifox when enabled and stale.

    The packaged api_catalog.json is a safe fallback. A refreshed catalog is saved
    under the user's cache directory, so new official interfaces can appear in the
    MCP tool list without requiring a new PyPI/GitHub release.

    Args:
        refresh: If True, check for updates from Apifox. If None, use environment setting.
        force_refresh: If True, always fetch from Apifox regardless of cache freshness.
    """
    if refresh is None:
        refresh = _catalog_auto_update_enabled()

    cached = _load_cached_catalog_data()
    
    if force_refresh:
        _log_catalog_event("catalog.refresh.force", reason="force_refresh enabled")
        try:
            fresh = refresh_catalog_from_apifox()
            _write_catalog_cache(fresh)
            _log_catalog_event("catalog.refresh.success", source="apifox", 
                              operations_count=len(fresh.get("operations", [])),
                              sha256=fresh.get("sha256"))
            return _ensure_tool_names(fresh)
        except Exception as e:
            _log_catalog_event("catalog.refresh.failed", error=str(e), fallback_to_cache=cached is not None)
            if cached is not None:
                return _ensure_tool_names(cached)
            raise

    if refresh and cached is not None and _cache_is_fresh(cached):
        _log_catalog_event("catalog.load.cache_fresh", 
                          sha256=cached.get("sha256"),
                          generated_at=cached.get("generated_at"))
        return _ensure_tool_names(cached)

    if refresh:
        _log_catalog_event("catalog.refresh.start", reason="cache stale or missing")
        try:
            fresh = refresh_catalog_from_apifox()
            _write_catalog_cache(fresh)
            _log_catalog_event("catalog.refresh.success", source="apifox",
                              operations_count=len(fresh.get("operations", [])),
                              sha256=fresh.get("sha256"))
            return _ensure_tool_names(fresh)
        except Exception as e:
            _log_catalog_event("catalog.refresh.failed", error=str(e), fallback_to_cache=cached is not None)
            if cached is not None:
                return _ensure_tool_names(cached)

    _log_catalog_event("catalog.load.packaged")
    return _ensure_tool_names(_load_packaged_catalog_data())


def load_catalog(*, refresh: bool | None = None, force_refresh: bool = False) -> Catalog:
    data = load_catalog_data(refresh=refresh, force_refresh=force_refresh)
    operations: list[Operation] = []
    for raw in data["operations"]:
        raw = dict(raw)
        tool_name = raw.pop("tool_name", None) or DOC_ID_TOOL_NAMES.get(raw["doc_id"])
        if not tool_name:
            tool_name = _stable_generated_tool_name(raw, {op.tool_name for op in operations})
        operations.append(Operation(tool_name=tool_name, **raw))
    return Catalog(operations=operations)


def operation_by_tool_name(catalog: Catalog, tool_name: str) -> Operation:
    for operation in catalog.operations:
        if operation.tool_name == tool_name:
            return operation
    raise KeyError(f"Unknown tool: {tool_name}")


def _dreamina_create_body_schema(schema: dict[str, Any]) -> dict[str, Any]:
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
        "base_url": {
            "type": "string",
            "description": "可选。LittleOrange API Base URL；不传时使用环境变量 LITTLEORANGE_BASE_URL，默认 https://vg-api.aig-ai.com。",
        },
        "api_key": {
            "type": "string",
            "description": "可选。LittleOrange 视频 API Key；不传时使用环境变量 LITTLEORANGE_API_KEY。不要在对话中泄露真实密钥。",
        },
        "headers": {
            "type": "object",
            "description": "可选。附加请求头；Authorization 会被忽略并始终由 api_key 生成。",
            "additionalProperties": {"type": "string"},
        },
        "query_params": {
            "type": "object",
            "description": "可选。附加查询参数；用于 raw/调试或文档尚未覆盖的扩展参数。",
            "additionalProperties": True,
        },
    }
    required: list[str] = []

    for param in operation.parameters:
        name = param["name"]
        properties[name] = _param_to_schema(param)
        if param.get("required") and name != "Action":
            required.append(name)

    if operation.body_schema is not None:
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
    example_hint = ""
    if operation.tool_name in {"vidu_t2v", "veo31_t2v", "dreamina_create_video"}:
        example_hint = "\n最小示例：传 model_id 和 request_body，request_body 至少包含模型名与 prompt/content。"
    return (
        f"{operation.folder} / {operation.summary}\n"
        f"HTTP: {operation.method} {operation.path}\n"
        f"路径/查询参数: {params_hint}{body_hint}{example_hint}\n"
        f"文档: {operation.doc_url}\n"
        "适用场景：当用户明确要创建/查询该模型任务时使用。注意：该工具会调用付费/限额 API。"
    )
