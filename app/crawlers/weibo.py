"""微博热搜榜。"""
from __future__ import annotations

from urllib.parse import quote

from .base import BaseCrawler, HotItem
from ..utils import parse_hot

API = "https://weibo.com/ajax/side/hotSearch"


class WeiboCrawler(BaseCrawler):
    platform = "weibo"
    platform_name = "微博热搜"

    def crawl(self, client, max_items: int) -> list[HotItem]:
        data = client.get_json(API, headers={"Referer": "https://weibo.com/"})
        if not isinstance(data, dict):
            return []
        rows = (data.get("data") or {}).get("realtime") or []
        result = []
        for index, row in enumerate(rows[:max_items], 1):
            title = row.get("word") or row.get("note") or ""
            if not title:
                continue
            rank = int(row.get("realpos") or row.get("rank") or index)
            result.append(
                HotItem(
                    platform=self.platform,
                    platform_name=self.platform_name,
                    rank=rank,
                    title=title,
                    url=f"https://s.weibo.com/weibo?q=%23{quote(str(title))}%23",
                    hot_value=parse_hot(row.get("num")),
                    hot_text=str(row.get("num") or ""),
                    label=row.get("label_name") or row.get("icon_desc") or "",
                    extra={"word_scheme": row.get("word_scheme", "")},
                )
            )
        return result
