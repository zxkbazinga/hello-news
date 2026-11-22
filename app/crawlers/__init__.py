"""各平台热榜抓取器。"""
from .bilibili import BilibiliCrawler
from .baidu import BaiduCrawler
from .douyin import DouyinCrawler
from .toutiao import ToutiaoCrawler
from .weibo import WeiboCrawler
from .zhihu import ZhihuCrawler

CRAWLERS = {
    "weibo": WeiboCrawler,
    "zhihu": ZhihuCrawler,
    "baidu": BaiduCrawler,
    "douyin": DouyinCrawler,
    "bilibili": BilibiliCrawler,
    "toutiao": ToutiaoCrawler,
}

DISPLAY_NAMES = {
    "weibo": "微博热搜",
    "zhihu": "知乎热榜",
    "baidu": "百度热搜",
    "douyin": "抖音热点",
    "bilibili": "B站热搜",
    "toutiao": "今日头条热榜",
}

__all__ = ["CRAWLERS", "DISPLAY_NAMES"]
