"""今日头条热榜。"""
from __future__ import annotations

from .base import BaseCrawler, HotItem
from ..utils import parse_hot

API = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"


class ToutiaoCrawler(BaseCrawler):
    platform = "toutiao"
    platform_name = "今日头条热榜"

    def crawl(self, client, max_items: int) -> list[HotItem]:
        data = client.get_json(API)
        if not isinstance(data, dict):
            return []
        rows = data.get("data") or []
        result = []
        for index, row in enumerate(rows[:max_items], 1):
            title = row.get("Title") or ""
            if not title:
                continue
            cluster_id = str(row.get("ClusterIdStr") or row.get("ClusterId") or "")
            url = row.get("Url") or (
                f"https://www.toutiao.com/trending/{cluster_id}/" if cluster_id else ""
            )
            result.append(
                HotItem(
                    platform=self.platform,
                    platform_name=self.platform_name,
                    rank=index,
                    title=title,
                    url=url,
                    hot_value=parse_hot(row.get("HotValue")),
                    hot_text=str(row.get("HotValue") or ""),
                    label=row.get("Label") or "",
                    item_key=cluster_id or "",
                )
            )
        return result
