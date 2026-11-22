"""抖音热点榜。"""
from __future__ import annotations

from .base import BaseCrawler, HotItem
from ..utils import ts_to_iso

API = (
    "https://www.douyin.com/aweme/v1/web/hot/search/list/"
    "?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1"
)


class DouyinCrawler(BaseCrawler):
    platform = "douyin"
    platform_name = "抖音热点"

    def crawl(self, client, max_items: int) -> list[HotItem]:
        data = client.get_json(API, headers={"Referer": "https://www.douyin.com/"})
        if not isinstance(data, dict):
            return []
        rows = (data.get("data") or {}).get("word_list") or []
        result = []
        for index, row in enumerate(rows[:max_items], 1):
            title = row.get("word") or ""
            if not title:
                continue
            sentence_id = str(row.get("sentence_id") or "")
            result.append(
                HotItem(
                    platform=self.platform,
                    platform_name=self.platform_name,
                    rank=int(row.get("position") or index),
                    title=title,
                    url=f"https://www.douyin.com/hot/{sentence_id}" if sentence_id else "",
                    hot_value=row.get("hot_value"),
                    hot_text=str(row.get("hot_value") or ""),
                    item_key=sentence_id or "",
                    published_at=ts_to_iso(row.get("event_time")),
                )
            )
        return result
