from __future__ import annotations

import asyncio
import time
from typing import Any

from .config import (
    DEFAULT_FIRST_POLL_DELAY_SECONDS,
    DEFAULT_MAX_POLL_ATTEMPTS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    LittleOrangeConfigError,
    get_debug_enabled,
    get_first_poll_delay_seconds,
    get_log_file,
    get_max_poll_attempts,
    get_poll_interval_seconds,
)

AUTO_POLL_TOOL_NAMES = [
    "sora2_t2v_wait",
    "sora2_i2v_wait",
    "veo31_t2v_wait",
    "veo31_i2v_wait",
    "veo31_extend_wait",
    "vidu_t2v_wait",
    "vidu_i2v_wait",
    "vidu_start_end_wait",
    "vidu_ref_subj_wait",
    "vidu_ref_wait",
    "dreamina_create_video_wait",
]

CREATE_TO_QUERY_TOOL = {
    "sora2_t2v": "sora2_query",
    "sora2_i2v": "sora2_query",
    "veo31_t2v": "veo31_query",
    "veo31_i2v": "veo31_query",
    "veo31_extend": "veo31_query",
    "vidu_t2v": "vidu_query",
    "vidu_i2v": "vidu_query",
    "vidu_start_end": "vidu_query",
    "vidu_ref_subj": "vidu_query",
    "vidu_ref": "vidu_query",
    "dreamina_create_video": "dreamina_query_video",
}

WAIT_TO_CREATE_TOOL = {
    "sora2_t2v_wait": "sora2_t2v",
    "sora2_i2v_wait": "sora2_i2v",
    "veo31_t2v_wait": "veo31_t2v",
    "veo31_i2v_wait": "veo31_i2v",
    "veo31_extend_wait": "veo31_extend",
    "vidu_t2v_wait": "vidu_t2v",
    "vidu_i2v_wait": "vidu_i2v",
    "vidu_start_end_wait": "vidu_start_end",
    "vidu_ref_subj_wait": "vidu_ref_subj",
    "vidu_ref_wait": "vidu_ref",
    "dreamina_create_video_wait": "dreamina_create_video",
}


def _log_debug(event: dict[str, Any]) -> None:
    if not get_debug_enabled():
        return
    path = get_log_file()
    if not path:
        return
    import json

    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def configured_poll_interval_seconds() -> float:
    return get_poll_interval_seconds()


def configured_max_poll_attempts() -> int:
    return get_max_poll_attempts()


def configured_first_poll_delay_seconds() -> float:
    return get_first_poll_delay_seconds()


def query_tool_for_create_tool(create_tool_name: str) -> str:
    return CREATE_TO_QUERY_TOOL[create_tool_name]


def create_tool_for_wait_tool(wait_tool_name: str) -> str:
    return WAIT_TO_CREATE_TOOL[wait_tool_name]


def wait_tool_for_create_tool(create_tool_name: str) -> str | None:
    for wait_name, create_name in WAIT_TO_CREATE_TOOL.items():
        if create_name == create_tool_name:
            return wait_name
    return None


def extract_task_id(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("task_id", "id", "name"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    nested = data.get("data")
    if isinstance(nested, dict):
        return extract_task_id(nested)
    return None


def extract_video_urls(data: Any) -> list[str]:
    urls: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value.startswith(("http://", "https://")) and value not in urls:
            urls.append(value)

    if not isinstance(data, dict):
        return urls

    add(data.get("download_url"))

    content = data.get("content")
    if isinstance(content, dict):
        add(content.get("video_url"))

    response = data.get("response")
    if isinstance(response, dict):
        for video in response.get("videos") or []:
            if isinstance(video, dict):
                add(video.get("gcsUri"))
                add(video.get("gcsuri"))
                add(video.get("url"))

    for creation in data.get("creations") or []:
        if isinstance(creation, dict):
            add(creation.get("url"))
            add(creation.get("watermarked_url"))

    return urls


def normalize_task_status(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"normalized_status": "unknown", "state": None, "status": None, "error": None}
    state = str(data.get("state", "") or "").lower() or None
    status = str(data.get("status", "") or "").lower() or None
    error = data.get("error")
    if state in {"failed", "fail", "error"} or status in {"failed", "fail", "error", "cancelled", "expired"}:
        return {"normalized_status": "failed", "state": state, "status": status, "error": error}
    if state == "success" or status in {"succeeded", "completed", "success"} or data.get("done") is True:
        return {"normalized_status": "success", "state": state, "status": status, "error": error}
    if extract_video_urls(data):
        return {"normalized_status": "success", "state": state, "status": status, "error": error}
    if any(key in data for key in ("state", "status", "progress", "done", "response", "content", "creations")):
        return {"normalized_status": "pending", "state": state, "status": status, "error": error}
    return {"normalized_status": "unknown", "state": state, "status": status, "error": error}


def is_terminal_success(data: Any) -> bool:
    return normalize_task_status(data)["normalized_status"] == "success"


def is_terminal_failure(data: Any) -> bool:
    return normalize_task_status(data)["normalized_status"] == "failed"


def format_poll_result(
    create_result: dict[str, Any],
    query_result: dict[str, Any],
    attempts: int,
    elapsed_seconds: float,
    poll_interval_seconds: float,
    max_poll_attempts: int,
    first_poll_delay_seconds: float,
) -> dict[str, Any]:
    urls = extract_video_urls(query_result)
    status_info = normalize_task_status(query_result)
    return {
        "status": "completed" if urls or status_info["normalized_status"] == "success" else "finished_without_video_url",
        "attempts": attempts,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "poll_interval_seconds": poll_interval_seconds,
        "max_poll_attempts": max_poll_attempts,
        "first_poll_delay_seconds": first_poll_delay_seconds,
        "task_id": extract_task_id(create_result) or extract_task_id(query_result),
        "video_urls": urls,
        "last_state": status_info.get("state"),
        "last_status": status_info.get("status"),
        "last_error": status_info.get("error"),
        "normalized_status": status_info["normalized_status"],
        "preview_hint": "TRAE/客户端如果支持 URL 预览，可直接打开或展示 video_urls 中的视频链接。MCP stdio 无法强制客户端内嵌播放，只能返回可展示的视频 URL。",
        "create_response": create_result,
        "final_query_response": query_result,
    }


async def poll_until_complete(
    create_result: dict[str, Any],
    query_call,
    *,
    max_attempts: int = DEFAULT_MAX_POLL_ATTEMPTS,
    interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    first_poll_delay_seconds: float = DEFAULT_FIRST_POLL_DELAY_SECONDS,
) -> dict[str, Any]:
    try:
        max_attempts = get_max_poll_attempts(max_attempts)
        interval_seconds = get_poll_interval_seconds(interval_seconds)
        first_poll_delay_seconds = get_first_poll_delay_seconds(first_poll_delay_seconds)
    except LittleOrangeConfigError as exc:
        return {
            "status": "error",
            "error_type": "validation_error",
            "message": str(exc),
            "details": {},
        }

    last: dict[str, Any] | None = None
    started = time.perf_counter()
    if first_poll_delay_seconds > 0:
        await asyncio.sleep(first_poll_delay_seconds)
    for attempt in range(1, max_attempts + 1):
        last = await query_call()
        status_info = normalize_task_status(last)
        _log_debug({
            "event": "poll.attempt",
            "attempt": attempt,
            "normalized_status": status_info["normalized_status"],
            "state": status_info.get("state"),
            "status": status_info.get("status"),
        })
        elapsed = time.perf_counter() - started
        if status_info["normalized_status"] == "success":
            assert last is not None
            return format_poll_result(
                create_result,
                last,
                attempt,
                elapsed,
                interval_seconds,
                max_attempts,
                first_poll_delay_seconds,
            )
        if status_info["normalized_status"] == "failed":
            return {
                "status": "failed",
                "attempts": attempt,
                "elapsed_seconds": round(elapsed, 3),
                "poll_interval_seconds": interval_seconds,
                "max_poll_attempts": max_attempts,
                "first_poll_delay_seconds": first_poll_delay_seconds,
                "task_id": extract_task_id(create_result) or extract_task_id(last),
                "video_urls": extract_video_urls(last),
                "last_state": status_info.get("state"),
                "last_status": status_info.get("status"),
                "last_error": status_info.get("error"),
                "normalized_status": status_info["normalized_status"],
                "create_response": create_result,
                "final_query_response": last,
            }
        if attempt < max_attempts:
            await asyncio.sleep(interval_seconds)
    elapsed = time.perf_counter() - started
    status_info = normalize_task_status(last)
    return {
        "status": "timeout",
        "error_type": "polling_timeout",
        "message": "轮询超时，任务在最大轮询次数内未完成。",
        "attempts": max_attempts,
        "elapsed_seconds": round(elapsed, 3),
        "poll_interval_seconds": interval_seconds,
        "max_poll_attempts": max_attempts,
        "first_poll_delay_seconds": first_poll_delay_seconds,
        "task_id": extract_task_id(create_result) or extract_task_id(last),
        "video_urls": extract_video_urls(last),
        "last_state": status_info.get("state"),
        "last_status": status_info.get("status"),
        "last_error": status_info.get("error"),
        "normalized_status": status_info["normalized_status"],
        "create_response": create_result,
        "final_query_response": last,
    }
