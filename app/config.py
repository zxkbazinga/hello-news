"""从环境变量读取配置，便于在 Docker 中调整。"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PLATFORMS = ("weibo", "zhihu", "baidu", "douyin", "bilibili", "toutiao")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _platforms() -> list[str]:
    raw = os.getenv("PLATFORMS", ",".join(DEFAULT_PLATFORMS))
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _run_time() -> tuple[int, int]:
    raw = os.getenv("RUN_TIME", "08:00").strip()
    try:
        hour, minute = (int(x) for x in raw.split(":"))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    except (ValueError, TypeError):
        pass
    return 8, 0


PLATFORMS: list[str] = _platforms()
RUN_HOUR, RUN_MINUTE = _run_time()
RUN_TIME = f"{RUN_HOUR:02d}:{RUN_MINUTE:02d}"
RUN_IMMEDIATELY = _bool("RUN_IMMEDIATELY", True)
DB_PATH = Path(os.getenv("DB_PATH", "/data/hotsearch.db"))
MAX_ITEMS = _int("MAX_ITEMS", 50)
REQUEST_TIMEOUT = _int("REQUEST_TIMEOUT", 15)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ZHIHU_COOKIE = os.getenv("ZHIHU_COOKIE", "").strip()

# Web 服务（供 iOS 等设备访问）
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = _int("WEB_PORT", 8080)

# 数据保留天数：只保留最近 N 个自然日（含当天）
RETENTION_DAYS = max(1, _int("RETENTION_DAYS", 3))

