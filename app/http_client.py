"""带重试和统一请求头的 HTTP 客户端。"""
from __future__ import annotations

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


class HttpClient:
    def __init__(self, timeout: int = 15, retries: int = 3):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_UA,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        retry = Retry(
            total=retries,
            backoff_factor=0.8,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_json(self, url: str, **kwargs: Any) -> dict | list | None:
        response = self._get(url, **kwargs)
        if response is None:
            return None
        try:
            return response.json()
        except ValueError:
            log.error("响应不是合法 JSON: %s", url)
            return None

    def get_text(self, url: str, **kwargs: Any) -> str | None:
        response = self._get(url, **kwargs)
        return response.text if response is not None else None

    def _get(self, url: str, **kwargs: Any) -> requests.Response | None:
        headers = kwargs.pop("headers", None)
        try:
            response = self.session.get(
                url, headers=headers, timeout=self.timeout, **kwargs
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            log.warning("请求失败 %s: %s", url, exc)
            return None

    def close(self) -> None:
        self.session.close()
