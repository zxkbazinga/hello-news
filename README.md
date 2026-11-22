# hello-news

一个用 Docker 部署的热榜聚合服务：每天自动抓取微博、知乎、百度、抖音、哔哩哔哩、今日头条的热榜，存入 SQLite，并通过一个针对 iPhone 优化过的 Web 页面 / PWA 展示。

- 六个平台热榜，单平台失败不影响其他平台
- 容器内定时抓取，默认每天 `08:00`，启动时可立即抓一次
- 只保留最近 3 个自然日的数据，过期自动清理
- 移动端页面适配 iOS Safari（安全区域、触摸目标、深色模式），可“添加到主屏幕”当 App 用
- 提供 JSON API，方便接自己的前端或快捷指令
- 镜像由 GitHub Actions 自动构建并发布到 GHCR

---

## 1. 快速开始：Docker Compose 部署（推荐）

适合想直接用现成镜像、不想克隆源码的情况。

新建目录并写入一个 `docker-compose.yml`：

```yaml
services:
  hotsearch:
    image: ghcr.io/zxkbazinga/hello-news:0.1.0
    container_name: hotsearch
    restart: unless-stopped
    ports:
      - "8080:8080"          # 宿主机端口:容器端口，被占用时改成 "8081:8080"
    environment:
      TZ: Asia/Shanghai
      RUN_TIME: "08:00"
      RUN_IMMEDIATELY: "true"
      RETENTION_DAYS: "3"
      WEB_HOST: "0.0.0.0"
      WEB_PORT: "8080"
    volumes:
      - ./data:/data         # 数据库保存在宿主机 ./data/hotsearch.db
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

然后：

```bash
mkdir -p data
docker compose up -d
docker compose logs -f        # 查看抓取日志
```

浏览器打开 `http://<运行Docker的机器IP>:8080`，看到页面即部署成功。

### 如果你想本地构建（改了代码时）

```bash
git clone git@github.com:zxkbazinga/hello-news.git
cd hello-news
mkdir -p data
docker compose up -d --build
```

仓库自带的 `docker-compose.yml` 里带 `build: .`，会优先用本地源码构建镜像。

---

## 2. 快速开始：docker run 部署

不需要 compose 文件，一条命令启动。

**Linux / macOS：**

```bash
mkdir -p data
docker run -d --name hotsearch \
  --restart unless-stopped \
  -p 8080:8080 \
  -v "$(pwd)/data:/data" \
  -e TZ=Asia/Shanghai \
  -e RETENTION_DAYS=3 \
  -e RUN_TIME=08:00 \
  ghcr.io/zxkbazinga/hello-news:0.1.0
```

**Windows PowerShell：**

```powershell
mkdir data
docker run -d --name hotsearch `
  --restart unless-stopped `
  -p 8080:8080 `
  -v "${PWD}/data:/data" `
  -e TZ=Asia/Shanghai `
  -e RETENTION_DAYS=3 `
  ghcr.io/zxkbazinga/hello-news:0.1.0
```

常用管理命令：

```bash
docker logs -f hotsearch                 # 看日志
docker restart hotsearch                 # 重启
docker stop hotsearch && docker rm hotsearch   # 停止并删除容器（数据仍在 ./data）
```

---

## 3. 在 iPhone 上使用（PWA）

1. 手机和跑 Docker 的机器连**同一个 WiFi**
2. Safari 打开 `http://<机器IP>:8080`
3. 点底部**分享**按钮 → **添加到主屏幕**
4. 桌面出现“热榜”图标，点开即全屏，跟 App 一样

说明：

- 页面、按钮、列表都针对 iOS Safari 做过适配，支持深色模式
- 点击任意条目跳转到原网站
- 页面右上角“↻ 刷新”可直接触发一次抓取
- **局域网 HTTP 下 Service Worker 的离线缓存不生效**（浏览器安全限制，仅 HTTPS / localhost 可用）。“添加到主屏幕”本身不受影响，联网时数据正常

> 如果手机连不上：确认服务监听 `0.0.0.0`、防火墙放行 8080 入站、手机和机器在同一网段。

---

## 4. 配置项

全部通过环境变量配置，compose 和 `docker run -e` 都可用。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TZ` | `Asia/Shanghai` | 容器时区，影响每日抓取时间 |
| `PLATFORMS` | `weibo,zhihu,baidu,douyin,bilibili,toutiao` | 要抓取的平台，逗号分隔，可裁剪 |
| `RUN_TIME` | `08:00` | 每天执行时间（24 小时制） |
| `RUN_IMMEDIATELY` | `true` | 容器启动后是否立刻抓一次 |
| `MAX_ITEMS` | `50` | 每个平台最多保留条数 |
| `REQUEST_TIMEOUT` | `15` | HTTP 请求超时（秒） |
| `DB_PATH` | `/data/hotsearch.db` | 数据库路径，容器内路径 |
| `RETENTION_DAYS` | `3` | 数据保留天数，只保留最近 N 个自然日 |
| `WEB_HOST` | `0.0.0.0` | Web 监听地址，手机访问需保持 `0.0.0.0` |
| `WEB_PORT` | `8080` | Web 监听端口，改 port 映射时右侧要同步改 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `ZHIHU_COOKIE` | 空 | 可选，知乎访问受限时填入自己的 Cookie |

改完配置后执行 `docker compose up -d` 重建容器即可生效。

---

## 5. API

| 接口 | 说明 |
| --- | --- |
| `GET /` | 热榜页面（PWA） |
| `GET /api/hot` | 全部平台最新热榜 |
| `GET /api/hot?platform=weibo` | 指定平台，如 `weibo` / `zhihu` / `baidu` / `douyin` / `bilibili` / `toutiao` |
| `GET /api/hot?date=2026-11-22` | 指定日期 |
| `GET /api/meta` | 可用日期、平台列表、保留天数 |
| `GET /health` | 健康检查，返回 `{"status":"ok"}` |
| `POST /api/refresh` | 手动触发一次抓取（无请求体） |

示例：

```bash
curl http://127.0.0.1:8080/api/hot?platform=weibo
curl http://127.0.0.1:8080/api/meta
curl -X POST http://127.0.0.1:8080/api/refresh
```

`/api/hot` 返回结构：

```json
{
  "date": "2026-11-22",
  "platform": "weibo",
  "count": 50,
  "items": [
    {
      "platform": "weibo",
      "platform_name": "微博热搜",
      "rank": 1,
      "title": "……",
      "url": "……",
      "hot_value": 1234567,
      "hot_text": "123万",
      "crawl_date": "2026-11-22"
    }
  ]
}
```

---

## 6. 命令行工具

在容器里执行（compose 方式）：

```bash
docker compose run --rm hotsearch python -m app.main --once    # 立刻抓一次
docker compose run --rm hotsearch python -m app.main --purge   # 只清理过期数据
docker compose run --rm hotsearch python -m app.main --stats   # 查看数据库统计
```

本地开发：

```bash
python -m pip install -r requirements.txt
DB_PATH=./data/hotsearch.db WEB_PORT=8080 python -m app.main
```

数据库是标准 SQLite，可以直接查询：

```sql
SELECT platform_name, rank, title, hot_value
FROM hot_items
WHERE crawl_date = '2026-11-22' AND platform = 'weibo'
ORDER BY rank LIMIT 10;
```

---

## 7. 镜像版本

镜像发布在 GitHub Container Registry：

```
ghcr.io/zxkbazinga/hello-news:0.1.0
ghcr.io/zxkbazinga/hello-news:0.1
ghcr.io/zxkbazinga/hello-news:latest
```

推送 `v*` 标签会触发 GitHub Actions 自动构建并发布新版本。想固定版本就用具体版本号，别用 `latest`。

本地构建：

```bash
docker build -t hotsearch-crawler:latest .
```

---

## 8. 数据来源与免责声明

数据来自各平台公开的热榜接口，仅用于个人学习和信息聚合。各平台接口随时可能调整，若某个平台持续抓取失败，通常是接口地址变了，修改 `app/crawlers/<平台>.py` 中的 URL 即可。请遵守各平台的使用条款，不要用于商业用途或大规模抓取。

---

## License

[MIT](LICENSE) © 2026 zxkbazinga
