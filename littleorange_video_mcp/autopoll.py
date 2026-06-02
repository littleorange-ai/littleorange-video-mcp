from __future__ import annotations

import asyncio
from typing import Any

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


def is_terminal_success(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    state = str(data.get("state", "")).lower()
    status = str(data.get("status", "")).lower()
    if state == "success":
        return True
    if status in {"succeeded", "completed", "success"}:
        return True
    if data.get("done") is True:
        return True
    return bool(extract_video_urls(data)) and not is_terminal_failure(data)


def is_terminal_failure(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    state = str(data.get("state", "")).lower()
    status = str(data.get("status", "")).lower()
    if state in {"failed", "fail", "error"}:
        return True
    if status in {"failed", "fail", "error", "cancelled", "expired"}:
        return True
    if data.get("error") and status not in {"succeeded", "completed", "success"}:
        return True
    return False


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


def format_poll_result(create_result: dict[str, Any], query_result: dict[str, Any], attempts: int) -> dict[str, Any]:
    urls = extract_video_urls(query_result)
    return {
        "status": "completed" if urls or is_terminal_success(query_result) else "finished_without_video_url",
        "attempts": attempts,
        "task_id": extract_task_id(create_result) or extract_task_id(query_result),
        "video_urls": urls,
        "preview_hint": "TRAE/客户端如果支持 URL 预览，可直接打开或展示 video_urls 中的视频链接。MCP stdio 无法强制客户端内嵌播放，只能返回可展示的视频 URL。",
        "create_response": create_result,
        "final_query_response": query_result,
    }


async def poll_until_complete(
    create_result: dict[str, Any],
    query_call,
    *,
    max_attempts: int = 60,
    interval_seconds: float = 5.0,
) -> dict[str, Any]:
    last: dict[str, Any] | None = None
    for attempt in range(1, max_attempts + 1):
        last = await query_call()
        if is_terminal_success(last):
            return format_poll_result(create_result, last, attempt)
        if is_terminal_failure(last):
            return {
                "status": "failed",
                "attempts": attempt,
                "task_id": extract_task_id(create_result) or extract_task_id(last),
                "video_urls": extract_video_urls(last),
                "create_response": create_result,
                "final_query_response": last,
            }
        if attempt < max_attempts:
            await asyncio.sleep(interval_seconds)
    return {
        "status": "timeout",
        "attempts": max_attempts,
        "task_id": extract_task_id(create_result) or extract_task_id(last),
        "video_urls": extract_video_urls(last),
        "create_response": create_result,
        "final_query_response": last,
    }
