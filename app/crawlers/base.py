"""抓取器基类与统一数据结构。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..utils import make_key


@dataclass
class HotItem:
    platform: str
    platform_name: str
    rank: int
    title: str
    url: str = ""
    hot_value: int | None = None
    hot_text: str = ""
    label: str = ""
    item_key: str = ""
    published_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def make_key(self) -> str:
        return make_key(self.platform, self.title)


class BaseCrawler:
    platform = ""
    platform_name = ""

    def crawl(self, client, max_items: int) -> list[HotItem]:
        raise NotImplementedError
