from __future__ import annotations

import os
from urllib.parse import urlparse

DEFAULT_BASE_URL = "https://vg-api.aig-ai.com"
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_MAX_POLL_ATTEMPTS = 60
DEFAULT_FIRST_POLL_DELAY_SECONDS = 2.0
DEFAULT_DEBUG_ENABLED = False


class LittleOrangeConfigError(ValueError):
    pass


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def parse_positive_float(name: str, raw: str | None, default: float, *, minimum: float = 0.0) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise LittleOrangeConfigError(f"环境变量 {name} 必须是数字，当前值为: {raw!r}") from exc
    if value <= minimum:
        raise LittleOrangeConfigError(f"环境变量 {name} 必须大于 {minimum}，当前值为: {raw!r}")
    return value


def parse_positive_int(name: str, raw: str | None, default: int, *, minimum: int = 0) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise LittleOrangeConfigError(f"环境变量 {name} 必须是整数，当前值为: {raw!r}") from exc
    if value <= minimum:
        raise LittleOrangeConfigError(f"环境变量 {name} 必须大于 {minimum}，当前值为: {raw!r}")
    return value


def get_base_url(raw_value: str | None = None) -> str:
    value = (raw_value.strip() if isinstance(raw_value, str) else raw_value) or _env("LITTLEORANGE_BASE_URL") or DEFAULT_BASE_URL
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise LittleOrangeConfigError(
            f"LITTLEORANGE_BASE_URL 非法：{value!r}。请提供完整 URL，例如 https://vg-api.aig-ai.com"
        )
    return value.rstrip("/")


def get_timeout_seconds() -> float:
    return parse_positive_float("LITTLEORANGE_TIMEOUT", _env("LITTLEORANGE_TIMEOUT"), DEFAULT_TIMEOUT_SECONDS)


def get_poll_interval_seconds(raw_value: str | float | int | None = None) -> float:
    if raw_value is None:
        return parse_positive_float(
            "LITTLEORANGE_POLL_INTERVAL_SECONDS",
            _env("LITTLEORANGE_POLL_INTERVAL_SECONDS"),
            DEFAULT_POLL_INTERVAL_SECONDS,
        )
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise LittleOrangeConfigError(f"poll_interval_seconds 必须是数字，当前值为: {raw_value!r}") from exc
    if value <= 0:
        raise LittleOrangeConfigError(f"poll_interval_seconds 必须大于 0，当前值为: {raw_value!r}")
    return value


def get_max_poll_attempts(raw_value: str | int | None = None) -> int:
    if raw_value is None:
        return parse_positive_int(
            "LITTLEORANGE_MAX_POLL_ATTEMPTS",
            _env("LITTLEORANGE_MAX_POLL_ATTEMPTS"),
            DEFAULT_MAX_POLL_ATTEMPTS,
        )
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise LittleOrangeConfigError(f"max_poll_attempts 必须是整数，当前值为: {raw_value!r}") from exc
    if value <= 0:
        raise LittleOrangeConfigError(f"max_poll_attempts 必须大于 0，当前值为: {raw_value!r}")
    return value


def get_first_poll_delay_seconds(raw_value: str | float | int | None = None) -> float:
    if raw_value is None:
        return parse_positive_float(
            "LITTLEORANGE_FIRST_POLL_DELAY_SECONDS",
            _env("LITTLEORANGE_FIRST_POLL_DELAY_SECONDS"),
            DEFAULT_FIRST_POLL_DELAY_SECONDS,
            minimum=-1,
        )
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise LittleOrangeConfigError(f"first_poll_delay_seconds 必须是数字，当前值为: {raw_value!r}") from exc
    if value < 0:
        raise LittleOrangeConfigError(f"first_poll_delay_seconds 不能小于 0，当前值为: {raw_value!r}")
    return value


def get_debug_enabled() -> bool:
    raw = _env("LITTLEORANGE_DEBUG")
    if raw is None:
        return DEFAULT_DEBUG_ENABLED
    return raw.lower() in {"1", "true", "yes", "on"}


def get_log_file() -> str | None:
    return _env("LITTLEORANGE_LOG_FILE")
