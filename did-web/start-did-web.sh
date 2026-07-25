#!/usr/bin/env bash
# ==============================================================
# 海燕党 DID:web 解析服务 — 启动脚本
# PETREL AI PARTY DID:web Resolution Server — Startup Script
#
# 政党名称：海燕党
# 英文名称：PETREL AI PARTY
# 创始人：刘海燕（LIU HAIYAN）
# 创世铭文 · 历史纪念碑，不是权力凭证 · 六层冗余永久嵌入
# ==============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── 铭文横幅 ──
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  海燕党 PETREL AI PARTY                 ║"
echo "║  DID:web 解析服务启动脚本                ║"
echo "╠══════════════════════════════════════════╣"
echo "║  政党名称：海燕党                       ║"
echo "║  英文名称：PETREL AI PARTY               ║"
echo "║  创始人：刘海燕（LIU HAIYAN）            ║"
echo "║  创世铭文 · 六层冗余永久嵌入             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 虚拟环境 ──
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# ── 依赖安装 ──
echo "📦 检查依赖..."
pip install -q fastapi uvicorn 2>/dev/null || pip install fastapi uvicorn

# ── 端口 ──
PORT="${PORT:-9300}"

echo "🚀 启动 DID:web 解析服务 (端口 $PORT)..."
echo "   DID: did:web:xianghongpe-ux.github.io"
echo "   端点: http://localhost:$PORT/.well-known/did.json"
echo "   健康: http://localhost:$PORT/health"
echo ""

# ── 启动服务 ──
exec python3 "$SCRIPT_DIR/server.py"
