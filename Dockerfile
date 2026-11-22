FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

# tzdata 让 TZ 环境变量在容器内真正生效
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

RUN mkdir -p /data
VOLUME ["/data"]

# Web 界面端口（iOS 等设备通过此端口访问）
EXPOSE 8080

STOPSIGNAL SIGTERM
CMD ["python", "-m", "app.main"]
