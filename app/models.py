"""SQLite 持久化：每次抓取一个 run，榜单条目去重入库。"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

from .utils import now_iso

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS crawl_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL DEFAULT 'running',
    platforms    TEXT NOT NULL DEFAULT '',
    total_items  INTEGER NOT NULL DEFAULT 0,
    error        TEXT
);

CREATE TABLE IF NOT EXISTS hot_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         INTEGER NOT NULL,
    platform       TEXT NOT NULL,
    platform_name  TEXT NOT NULL,
    rank           INTEGER NOT NULL,
    title          TEXT NOT NULL,
    url            TEXT NOT NULL DEFAULT '',
    hot_value      INTEGER,
    hot_text       TEXT NOT NULL DEFAULT '',
    label          TEXT NOT NULL DEFAULT '',
    item_key       TEXT NOT NULL,
    published_at   TEXT,
    crawled_at     TEXT NOT NULL,
    crawl_date     TEXT NOT NULL,
    extra          TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (run_id) REFERENCES crawl_runs(id),
    UNIQUE (crawl_date, platform, item_key)
);

CREATE INDEX IF NOT EXISTS idx_hot_items_platform_date
    ON hot_items(platform, crawl_date);
CREATE INDEX IF NOT EXISTS idx_hot_items_run_id
    ON hot_items(run_id);
CREATE INDEX IF NOT EXISTS idx_hot_items_title
    ON hot_items(title);
"""


class Store:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)
            conn.commit()
        log.info("数据库就绪: %s", self.db_path)

    def start_run(self, platforms: Iterable[str]) -> int:
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "INSERT INTO crawl_runs (started_at, status, platforms) VALUES (?, 'running', ?)",
                (now_iso(), ",".join(platforms)),
            )
            conn.commit()
            return int(cur.lastrowid)

    def save_items(self, run_id: int, items: Iterable, crawled_at: str) -> int:
        from .crawlers.base import HotItem

        rows = []
        for item in items:
            if not isinstance(item, HotItem) or not item.title:
                continue
            key = item.item_key or item.make_key()
            rows.append(
                (
                    run_id,
                    item.platform,
                    item.platform_name,
                    item.rank,
                    item.title,
                    item.url or "",
                    item.hot_value,
                    item.hot_text or "",
                    item.label or "",
                    key,
                    item.published_at or "",
                    crawled_at,
                    crawled_at[:10],
                    json.dumps(item.extra or {}, ensure_ascii=False),
                )
            )
        if not rows:
            return 0
        with closing(self._connect()) as conn:
            before = conn.total_changes
            # 同一天同条目只保留一行，但用最新一次抓取的排名和热度覆盖旧值
            conn.executemany(
                """INSERT INTO hot_items
                   (run_id, platform, platform_name, rank, title, url, hot_value,
                    hot_text, label, item_key, published_at, crawled_at, crawl_date, extra)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(crawl_date, platform, item_key) DO UPDATE SET
                       rank=excluded.rank,
                       hot_value=excluded.hot_value,
                       hot_text=excluded.hot_text,
                       label=excluded.label,
                       url=excluded.url,
                       run_id=excluded.run_id,
                       crawled_at=excluded.crawled_at""",
                rows,
            )
            conn.commit()
            return conn.total_changes - before

    def finish_run(
        self,
        run_id: int,
        status: str,
        total_items: int,
        error: str | None = None,
    ) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """UPDATE crawl_runs
                   SET finished_at=?, status=?, total_items=?, error=?
                   WHERE id=?""",
                (now_iso(), status, total_items, error, run_id),
            )
            conn.commit()

    def purge_old(self, days: int) -> dict:
        """删除超过保留期的数据，只保留最近 days 个自然日（含当天）。"""
        cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
        with closing(self._connect()) as conn:
            # 先删子表再删主表，避免外键约束冲突
            deleted_items = conn.execute(
                "DELETE FROM hot_items WHERE crawl_date < ?", (cutoff,)
            ).rowcount
            deleted_runs = conn.execute(
                "DELETE FROM crawl_runs WHERE substr(started_at, 1, 10) < ?", (cutoff,)
            ).rowcount
            conn.commit()
            if deleted_items or deleted_runs:
                conn.execute("VACUUM")  # 回收磁盘空间，避免数据库文件持续增长
        return {
            "cutoff": cutoff,
            "deleted_items": deleted_items,
            "deleted_runs": deleted_runs,
        }

    def dates(self) -> list[str]:
        with closing(self._connect()) as conn:
            return [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT crawl_date FROM hot_items ORDER BY crawl_date DESC"
                )
            ]

    def platforms(self) -> list[dict]:
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            return [
                dict(row)
                for row in conn.execute(
                    """SELECT platform, platform_name, COUNT(*) AS count, MAX(crawl_date) AS latest
                       FROM hot_items GROUP BY platform ORDER BY platform"""
                )
            ]

    def latest_items(
        self, platform: str | None = None, day: str | None = None, limit: int = 200
    ) -> list[dict]:
        with closing(self._connect()) as conn:
            conn.row_factory = sqlite3.Row
            if day is None:
                row = conn.execute("SELECT MAX(crawl_date) FROM hot_items").fetchone()
                day = row[0] if row else None
            if not day:
                return []
            sql = """SELECT platform, platform_name, rank, title, url, hot_value,
                            hot_text, label, crawl_date
                     FROM hot_items WHERE crawl_date = ?"""
            params: list = [day]
            if platform:
                sql += " AND platform = ?"
                params.append(platform)
            sql += " ORDER BY platform, rank ASC LIMIT ?"
            params.append(limit)
            return [dict(row) for row in conn.execute(sql, params)]

    def stats(self) -> dict:
        with closing(self._connect()) as conn:
            runs = conn.execute("SELECT COUNT(*) FROM crawl_runs").fetchone()[0]
            items = conn.execute("SELECT COUNT(*) FROM hot_items").fetchone()[0]
            by_platform = conn.execute(
                """SELECT platform, platform_name, COUNT(*), MAX(crawl_date)
                   FROM hot_items GROUP BY platform ORDER BY platform"""
            ).fetchall()
            latest = conn.execute(
                "SELECT started_at, status, total_items FROM crawl_runs ORDER BY id DESC LIMIT 5"
            ).fetchall()
        return {
            "runs": runs,
            "items": items,
            "by_platform": by_platform,
            "latest_runs": latest,
        }
