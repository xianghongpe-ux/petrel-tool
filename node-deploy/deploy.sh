#!/usr/bin/env bash
# ============================================================
# 海燕党 · DZN 分布式AI网络 — 一键部署脚本
# ============================================================
# 创世铭文: 天下兴亡，匹夫有责。算力虽微，众志可城。
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
DZN_DIR="$PROJECT_ROOT/../../03-model/dzn"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     海燕党 · DZN 分布式AI网络 一键部署                  ║"
echo "║     创世铭文: 天下兴亡，匹夫有责。算力虽微，众志可城。   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── 环境检测 ────────────────────────────────────────────
echo -e "${YELLOW}[1/6] 检测运行环境...${NC}"

if ! command -v docker &>/dev/null; then
    echo -e "${RED}❌ 需要安装 Docker${NC}"
    echo "  安装指南: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
    echo -e "${RED}❌ 需要安装 docker-compose${NC}"
    exit 1
fi

DOCKER_COMPOSE="docker-compose"
if docker compose version &>/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
fi

echo -e "${GREEN}✓ Docker 已安装${NC}"

# ── 准备 DZN 核心代码 ───────────────────────────────────
echo -e "${YELLOW}[2/6] 准备 DZN 核心代码...${NC}"

if [ -d "$DZN_DIR" ]; then
    # 复制 DZN 代码到部署目录
    cp -r "$DZN_DIR" "$PROJECT_ROOT/dzn/"
    echo -e "${GREEN}✓ DZN 核心代码已就绪${NC}"
else
    echo -e "${YELLOW}⚠ DZN 目录不存在: $DZN_DIR"
    echo "   将创建占位 Python 包${NC}"
    mkdir -p "$PROJECT_ROOT/dzn"
    for f in dzn_scheduler.py model_consensus.py ai_output_lock.py inference_node.py; do
        if [ -f "$PROJECT_ROOT/$f" ]; then
            cp "$PROJECT_ROOT/$f" "$PROJECT_ROOT/dzn/"
        fi
    done
    touch "$PROJECT_ROOT/dzn/__init__.py"
fi

# ── 拉取基础镜像 ─────────────────────────────────────────
echo -e "${YELLOW}[3/6] 拉取基础镜像...${NC}"
docker pull python:3.11-slim
docker pull python:3.11-alpine
docker pull nginx:alpine
echo -e "${GREEN}✓ 基础镜像已就绪${NC}"

# ── 构建服务镜像 ────────────────────────────────────────
echo -e "${YELLOW}[4/6] 构建 DZN 服务镜像...${NC}"

echo "  构建 dzn-gateway ..."
docker build --target gateway -t dzn-gateway "$PROJECT_ROOT" 2>&1 | tail -3

echo "  构建 dzn-voting ..."
docker build --target voting -t dzn-voting "$PROJECT_ROOT" 2>&1 | tail -3

echo "  构建 dzn-market ..."
docker build --target market -t dzn-market "$PROJECT_ROOT" 2>&1 | tail -3

echo "  构建 dzn-dashboard ..."
docker build --target dashboard -t dzn-dashboard "$PROJECT_ROOT" 2>&1 | tail -3

echo -e "${GREEN}✓ 所有镜像构建完成${NC}"

# ── 启动服务 ────────────────────────────────────────────
echo -e "${YELLOW}[5/6] 启动 DZN 网络...${NC}"

# 创建 .env 文件（如不存在）
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    cat > "$PROJECT_ROOT/.env" << EOF
# DZN 网络配置
DZN_LOG_LEVEL=info
DZN_GATEWAY_PORT=8765
DZN_VOTING_PORT=9101
DZN_MARKET_PORT=9102
DZN_DASHBOARD_PORT=9103
DZN_NGINX_PORT=80
DZN_VOTING_MIN_SIGNATURES=3
DZN_DASHBOARD_REFRESH=30
TZ=UTC
EOF
    echo -e "${GREEN}✓ 已创建 .env 配置文件${NC}"
fi

$DOCKER_COMPOSE -f "$PROJECT_ROOT/docker-compose.yml" up -d 2>&1

echo -e "${GREEN}✓ DZN 网络已启动${NC}"

# ── 验证部署 ────────────────────────────────────────────
echo -e "${YELLOW}[6/6] 验证部署...${NC}"
sleep 5

# 健康检查
SERVICES=(
    "网关:8765/p2p/ping"
    "投票:9101/health"
    "市场:9102"
    "看板:9103/health"
)

ALL_OK=true
for svc in "${SERVICES[@]}"; do
    NAME="${svc%%:*}"
    PORT="${svc##*:}"
    URL="${svc#*:}"
    if curl -sf "http://localhost:${URL}" >/dev/null 2>&1; then
        echo -e "${GREEN}  ✓ $NAME (:$PORT) 运行正常${NC}"
    else
        echo -e "${RED}  ✗ $NAME (:$PORT) 未响应${NC}"
        ALL_OK=false
    fi
done

echo ""
if $ALL_OK; then
    echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ DZN 分布式AI网络部署成功！                ║${NC}"
    echo -e "${GREEN}╠════════════════════════════════════════════════╣${NC}"
    echo -e "${GREEN}║  网关   : http://localhost:8765                ║${NC}"
    echo -e "${GREEN}║  投票   : http://localhost:9101                ║${NC}"
    echo -e "${GREEN}║  市场   : http://localhost:9102                ║${NC}"
    echo -e "${GREEN}║  看板   : http://localhost:9103                ║${NC}"
    echo -e "${GREEN}║  Nginx  : http://localhost                     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
else
    echo -e "${RED}部分服务未就绪，请检查日志: docker-compose logs${NC}"
fi

# ── 命令提示 ────────────────────────────────────────────
echo ""
echo -e "${CYAN}常用命令:${NC}"
echo "  查看日志:  $DOCKER_COMPOSE -f $PROJECT_ROOT/docker-compose.yml logs -f"
echo "  停止服务:  $DOCKER_COMPOSE -f $PROJECT_ROOT/docker-compose.yml down"
echo "  重启服务:  $DOCKER_COMPOSE -f $PROJECT_ROOT/docker-compose.yml restart"
echo "  重新构建:  $DOCKER_COMPOSE -f $PROJECT_ROOT/docker-compose.yml build"
echo ""
echo -e "${CYAN}创世铭文: 天下兴亡，匹夫有责。算力虽微，众志可城。${NC}"
