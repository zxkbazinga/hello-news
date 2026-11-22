"""知乎热榜。ZHIHU_COOKIE 可选，用于提升稳定性。"""
from __future__ import annotations

import os
import re

from .base import BaseCrawler, HotItem
from ..utils import parse_hot, ts_to_iso

API = "https://api.zhihu.com/topstory/hot-lists/total?limit=50"


class ZhihuCrawler(BaseCrawler):
    platform = "zhihu"
    platform_name = "知乎热榜"

    def crawl(self, client, max_items: int) -> list[HotItem]:
        headers = {"Referer": "https://www.zhihu.com/hot"}
        cookie = os.getenv("ZHIHU_COOKIE", "").strip()
        if cookie:
            headers["Cookie"] = cookie
        data = client.get_json(API, headers=headers)
        if not isinstance(data, dict):
            return []
        rows = data.get("data") or []
        result = []
        for index, row in enumerate(rows[:max_items], 1):
            target = row.get("target") or {}
            title = target.get("title") or ""
            if not title:
                continue
            item_id = str(target.get("id") or "")
            item_type = target.get("type") or "question"
            if item_type == "article":
                url = f"https://zhuanlan.zhihu.com/p/{item_id}"
            else:
                url = f"https://www.zhihu.com/question/{item_id}"
            detail = row.get("detail_text") or ""
            result.append(
                HotItem(
                    platform=self.platform,
                    platform_name=self.platform_name,
                    rank=index,
                    title=title,
                    url=url,
                    hot_value=parse_hot(detail),
                    hot_text=detail,
                    item_key=item_id or "",
                    published_at=ts_to_iso(target.get("created")),
                    extra={"answer_count": target.get("answer_count", 0)},
                )
            )
        return result
