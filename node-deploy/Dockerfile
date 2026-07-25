# ============================================================
# 海燕党 · DZN 分布式AI网络 — 多目标 Dockerfile
# ============================================================
# 创世铭文: 天下兴亡，匹夫有责。算力虽微，众志可城。
# ============================================================
# 构建方式:
#   docker build --target gateway -t dzn-gateway .
#   docker build --target voting  -t dzn-voting  .
#   docker build --target market  -t dzn-market  .
#   docker build --target dashboard -t dzn-dashboard .
# ============================================================

# ── 基础镜像 ───────────────────────────────────────────
FROM python:3.11-slim AS base

LABEL org.petrel.dzn.version="1.0.0"
LABEL org.petrel.dzn.genesis="天下兴亡，匹夫有责。算力虽微，众志可城。"

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# DZN 核心代码
COPY dzn/ ./dzn/

ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

# ── 通信网关 ───────────────────────────────────────────
FROM base AS gateway

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD curl -f http://localhost:8765/p2p/ping || exit 1

ENTRYPOINT ["python", "-m", "dzn.dzn_scheduler"]
CMD ["--port", "8765"]

# ── 投票客户端 ─────────────────────────────────────────
FROM base AS voting

EXPOSE 9101

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD curl -f http://localhost:9101/health || exit 1

ENTRYPOINT ["python", "-c", ""]
CMD ["sh", "-c", "python -c \"from dzn.ai_output_lock import main; main()\" --demo & \
                  exec python -m http.server 9101"]

# ── 任务市场前端 ──────────────────────────────────────
FROM python:3.11-alpine AS market

LABEL org.petrel.dzn.service="market"

WORKDIR /app

RUN apk add --no-cache curl

COPY market-frontend/ ./market-frontend/

EXPOSE 9102

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=5s \
  CMD curl -f http://localhost:9102/ || exit 1

CMD ["python", "-m", "http.server", "9102", "--directory", "market-frontend"]

# ── 社区健康度看板 ─────────────────────────────────────
FROM python:3.11-alpine AS dashboard

LABEL org.petrel.dzn.service="dashboard"

WORKDIR /app

RUN apk add --no-cache curl

COPY dashboard/ ./dashboard/

EXPOSE 9103

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
  CMD curl -f http://localhost:9103/health || exit 1

ENTRYPOINT ["python", "-m", "dashboard.server"]
CMD ["--port", "9103"]
