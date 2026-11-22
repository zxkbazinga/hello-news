"""百度热搜榜：页面内嵌 s-data 注释中解析 JSON。"""
from __future__ import annotations

import json
import re

from .base import BaseCrawler, HotItem
from ..utils import parse_hot

URL = "https://top.baidu.com/board?tab=realtime"
PATTERN = re.compile(r"<!--s-data:(.*?)-->", re.S)


class BaiduCrawler(BaseCrawler):
    platform = "baidu"
    platform_name = "百度热搜"

    def crawl(self, client, max_items: int) -> list[HotItem]:
        html = client.get_text(URL)
        if not html:
            return []
        match = PATTERN.search(html)
        if not match:
            return []
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []
        cards = (payload.get("data") or {}).get("cards") or payload.get("cards") or []
        if not cards:
            return []
        rows = cards[0].get("content") or []
        result = []
        for index, row in enumerate(rows[:max_items], 1):
            title = row.get("word") or row.get("query") or ""
            if not title:
                continue
            result.append(
                HotItem(
                    platform=self.platform,
                    platform_name=self.platform_name,
                    rank=index,
                    title=title,
                    url=row.get("rawUrl") or row.get("url") or "",
                    hot_value=parse_hot(row.get("hotScore")),
                    hot_text=str(row.get("hotScore") or ""),
                    label=row.get("hotTag") or "",
                    extra={"desc": row.get("desc", ""), "hotChange": row.get("hotChange", "")},
                )
            )
        return result
