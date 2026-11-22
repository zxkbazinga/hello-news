"""通用解析工具。"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    """返回带时区的当前时间（ISO 8601）。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def ts_to_iso(value: Any) -> str:
    """把 Unix 秒级时间戳转为 UTC ISO 字符串。"""
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return ""


def parse_hot(value: Any) -> int | None:
    """把 '7904442' / '2060 万热度' / '1.2亿' 等转成整数。"""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*(万|亿|w|W|k|K)?", text)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2)
    factor = {
        "万": 10_000,
        "亿": 100_000_000,
        "w": 10_000,
        "W": 10_000,
        "k": 1_000,
        "K": 1_000,
    }.get(unit, 1)
    return int(number * factor)


def make_key(*parts: Any) -> str:
    """生成稳定的去重键；优先使用平台 ID，否则退化为标题哈希。"""
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
