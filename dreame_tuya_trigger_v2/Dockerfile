# 直接使用 Docker Hub 多架构 Python 镜像，避免依赖 r.hassbus.com 等不可用基础镜像
FROM python:3.11-slim

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/
COPY run.sh /run.sh
RUN chmod +x /run.sh

LABEL \
    io.hass.version="1.0.1" \
    io.hass.type="addon" \
    io.hass.arch="armhf|armv7|aarch64|i386|amd64"

CMD [ "/run.sh" ]
