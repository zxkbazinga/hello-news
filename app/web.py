"""轻量 Web 服务：给 iOS 等设备提供热榜页面、JSON API 与 PWA 静态资源。"""
from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, unquote, urlparse

from . import config
from .models import Store

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"
REFRESH_CALLBACK = None  # 由 main.py 注入，避免循环导入

STATIC_TYPES = {
    ".webmanifest": "application/manifest+json",
    ".js": "application/javascript; charset=utf-8",
    ".png": "image/png",
    ".html": "text/html; charset=utf-8",
}


class HotHandler(BaseHTTPRequestHandler):
    server_version = "HotNews/1.0"
    store: Store

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/refresh":
            self._error(404, "Not Found")
            return
        if REFRESH_CALLBACK is None:
            self._error(503, "刷新功能不可用")
            return
        try:
            count = REFRESH_CALLBACK()
            self._json({"status": "ok", "count": count})
        except Exception:
            log.exception("手动刷新失败")
            self._error(500, "刷新失败")

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path in ("/", "/index.html"):
                self._head(STATIC_DIR / "index.html", "text/html; charset=utf-8", "no-store, max-age=0")
            elif path == "/manifest.webmanifest":
                self._head(STATIC_DIR / "manifest.webmanifest", "application/manifest+json", "public, max-age=86400")
            elif path == "/sw.js":
                self._head(STATIC_DIR / "sw.js", "application/javascript; charset=utf-8", "no-cache")
            elif path.startswith("/icons/"):
                name = path[len("/icons/"):]
                target = (STATIC_DIR / "icons" / name).resolve()
                if target.is_relative_to(STATIC_DIR.resolve()) and target.is_file():
                    self._head(target, "image/png", "public, max-age=604800")
                else:
                    self.send_error(404)
            else:
                self.send_error(404)
        except Exception:
            self.send_error(500)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path in ("/", "/index.html"):
                self._static("index.html", "no-store, max-age=0")
            elif path == "/manifest.webmanifest":
                self._static("manifest.webmanifest", "public, max-age=86400")
            elif path == "/sw.js":
                self._static("sw.js", "no-cache")
            elif path.startswith("/icons/"):
                self._static("icons/" + path[len("/icons/"):], "public, max-age=604800")
            elif path == "/api/hot":
                query = parse_qs(parsed.query)
                platform = query.get("platform", [None])[0]
                day = query.get("date", [None])[0]
                items = self.store.latest_items(platform, day)
                self._json(
                    {
                        "date": day or (items[0]["crawl_date"] if items else None),
                        "platform": platform or "all",
                        "count": len(items),
                        "items": items,
                    }
                )
            elif path == "/api/meta":
                self._json(
                    {
                        "dates": self.store.dates(),
                        "platforms": self.store.platforms(),
                        "retention_days": config.RETENTION_DAYS,
                    }
                )
            elif path == "/health":
                self._json({"status": "ok"})
            else:
                self._error(404, "Not Found")
        except Exception:
            log.exception("处理请求失败: %s", self.path)
            self._error(500, "Internal Server Error")

    def _json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(200, body, "application/json; charset=utf-8")

    def _static(self, rel: str, cache: str) -> None:
        """从 static 目录提供文件，带路径穿越防护。"""
        rel = unquote(rel).lstrip("/")
        base = STATIC_DIR.resolve()
        target = (base / rel).resolve()
        if not target.is_relative_to(base) or not target.is_file():
            self._error(404, "Not Found")
            return
        ctype = STATIC_TYPES.get(target.suffix.lower(), "application/octet-stream")
        headers = {"Cache-Control": cache}
        if target.name == "sw.js":
            headers["Service-Worker-Allowed"] = "/"
        self._send(200, target.read_bytes(), ctype, headers=headers)

    def _send(self, status: int, body: bytes, content_type: str, headers: dict | None = None) -> None:
        extra = headers or {}
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in extra.items():
            self.send_header(key, value)
        if not any(k.lower() == "cache-control" for k in extra):
            self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(body)

    def _head(self, path: Path, content_type: str, cache: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()

    def _error(self, status: int, message: str) -> None:
        self._send(status, message.encode("utf-8"), "text/plain; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:
        log.debug("HTTP %s - %s", self.address_string(), fmt % args)


def start_web(store: Store, refresh_callback=None) -> tuple[ThreadingHTTPServer, Thread]:
    """在后台线程启动 Web 服务，返回服务器与线程对象。"""
    global REFRESH_CALLBACK
    REFRESH_CALLBACK = refresh_callback
    handler = type("BoundHandler", (HotHandler,), {"store": store})
    server = ThreadingHTTPServer((config.WEB_HOST, config.WEB_PORT), handler)
    thread = Thread(target=server.serve_forever, name="web-server", daemon=True)
    thread.start()
    log.info("Web 服务已启动: http://%s:%d", config.WEB_HOST, config.WEB_PORT)
    return server, thread
