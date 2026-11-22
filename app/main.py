"""入口：Web 服务、定时抓取、过期数据清理与命令行工具。"""
from __future__ import annotations

import argparse
import logging
import signal
import time
from datetime import datetime, timedelta
from threading import Lock

from . import config
from .crawlers import CRAWLERS
from .http_client import HttpClient
from .models import Store
from .utils import now_iso
from .web import start_web

log = logging.getLogger("hotsearch")
_stop = False
_crawl_lock = Lock()  # 防止定时抓取和手动刷新同时写库


def _handle_stop(signum, frame) -> None:
    global _stop
    _stop = True
    log.info("收到停止信号，准备退出")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def purge(store: Store) -> dict:
    result = store.purge_old(config.RETENTION_DAYS)
    if result["deleted_items"] or result["deleted_runs"]:
        log.info(
            "清理过期数据：删除 %d 条榜单、%d 次抓取记录（保留 %s 起）",
            result["deleted_items"], result["deleted_runs"], result["cutoff"],
        )
    return result


def run_once(store: Store) -> int:
    """抓取一次并清理过期数据；带锁，避免重复并发执行。"""
    with _crawl_lock:
        return _do_crawl(store)


def _do_crawl(store: Store) -> int:
    client = HttpClient(timeout=config.REQUEST_TIMEOUT)
    run_id = store.start_run(config.PLATFORMS)
    started_at = now_iso()
    total = 0
    errors: list[str] = []

    try:
        for name in config.PLATFORMS:
            crawler_cls = CRAWLERS.get(name)
            if crawler_cls is None:
                log.error("未知平台: %s", name)
                errors.append(f"{name}: 未知平台")
                continue
            crawler = crawler_cls()
            try:
                items = crawler.crawl(client, config.MAX_ITEMS)
                saved = store.save_items(run_id, items, started_at)
                total += saved
                log.info("%s：抓取 %d 条，写入/更新 %d 条", crawler.platform_name, len(items), saved)
            except Exception as exc:  # 单个平台失败不影响其他平台
                log.exception("%s 抓取失败", crawler.platform_name)
                errors.append(f"{name}: {exc}")
    finally:
        client.close()

    status = "failed" if total == 0 and errors else ("partial" if errors else "success")
    store.finish_run(run_id, status, total, "; ".join(errors) or None)
    purge(store)
    log.info("本次抓取结束：共 %d 条，状态 %s", total, status)
    return total


def _sleep_until(target: datetime) -> None:
    while not _stop:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 1.0))


def serve(store: Store) -> None:
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    purge(store)  # 启动时先清理一次，防止长期停机期间积累旧数据
    server, _ = start_web(store, refresh_callback=lambda: run_once(store))

    if config.RUN_IMMEDIATELY:
        log.info("启动时立即执行一次抓取")
        run_once(store)

    try:
        while not _stop:
            now = datetime.now()
            target = now.replace(
                hour=config.RUN_HOUR, minute=config.RUN_MINUTE, second=0, microsecond=0
            )
            if target <= now:
                target += timedelta(days=1)
            log.info("下次抓取时间：%s", target.strftime("%Y-%m-%d %H:%M:%S"))
            _sleep_until(target)
            if not _stop:
                run_once(store)
    finally:
        server.shutdown()
        server.server_close()
        log.info("Web 服务与调度器已停止")


def show_stats(store: Store) -> None:
    data = store.stats()
    print(f"数据库：{store.db_path}")
    print(f"抓取次数：{data['runs']}    榜单条目：{data['items']}")
    print("\n按平台统计：")
    for platform, name, count, latest in data["by_platform"]:
        print(f"  {name:<12} {count:>6} 条   最近日期 {latest or '-'}")
    print("\n最近 5 次抓取：")
    for started, status, total in data["latest_runs"]:
        print(f"  {started}  {status:<8} {total} 条")


def main() -> None:
    parser = argparse.ArgumentParser(description="各大平台热榜抓取与 Web 展示服务")
    parser.add_argument("--once", action="store_true", help="只抓取一次后退出")
    parser.add_argument("--stats", action="store_true", help="查看数据库统计后退出")
    parser.add_argument("--purge", action="store_true", help="只清理过期数据后退出")
    args = parser.parse_args()

    setup_logging(config.LOG_LEVEL)
    store = Store(config.DB_PATH)
    log.info(
        "平台：%s | 每日执行：%s | 每榜条数：%d | 数据保留：%d 天",
        ",".join(config.PLATFORMS), config.RUN_TIME, config.MAX_ITEMS, config.RETENTION_DAYS,
    )

    if args.stats:
        show_stats(store)
    elif args.purge:
        print(purge(store))
    elif args.once:
        run_once(store)
    else:
        serve(store)


if __name__ == "__main__":
    main()
