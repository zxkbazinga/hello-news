"""B 站热搜词榜（search/square，无需 WBI 签名）。"""
from __future__ import annotations

from urllib.parse import quote

from .base import BaseCrawler, HotItem

API = "https://api.bilibili.com/x/web-interface/search/square?limit=50"


class BilibiliCrawler(BaseCrawler):
    platform = "bilibili"
    platform_name = "B站热搜"

    def crawl(self, client, max_items: int) -> list[HotItem]:
        data = client.get_json(API, headers={"Referer": "https://www.bilibili.com/"})
        if not isinstance(data, dict) or data.get("code") != 0:
            return []
        rows = ((data.get("data") or {}).get("trending") or {}).get("list") or []
        result = []
        for index, row in enumerate(rows[:max_items], 1):
            title = row.get("show_name") or row.get("keyword") or ""
            if not title:
                continue
            uri = row.get("uri") or ""
            url = uri if uri.startswith("http") else f"https://search.bilibili.com/all?keyword={quote(str(title))}"
            result.append(
                HotItem(
                    platform=self.platform,
                    platform_name=self.platform_name,
                    rank=index,
                    title=title,
                    url=url,
                    hot_value=row.get("heat_score"),
                    hot_text=str(row.get("heat_score") or ""),
                    item_key=str(title),
                    extra={"keyword": row.get("keyword", "")},
                )
            )
        return result
