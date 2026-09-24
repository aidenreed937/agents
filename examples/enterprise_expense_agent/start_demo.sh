#!/usr/bin/env bash
# 一键启动前后端分离示例脚本（FastAPI 后端 + Web 前端）

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN=".venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

echo "============================================================"
echo "Enterprise Expense Agent · 前后端分离示例快速启动"
echo "============================================================"

# 1. 后台启动 FastAPI 后端服务 (端口 8000)
echo "[1/2] 正在启动后端 FastAPI 服务 (Port: 8000)..."
$PYTHON_BIN examples/enterprise_expense_agent/server.py --port 8000 &
BACKEND_PID=$!

# 等待后端准备就绪
sleep 1.5

# 2. 检查并启动前端 React 控制台服务 (端口 3000)
FRONTEND_DIR="examples/enterprise_expense_agent/frontend"
if [ ! -d "$FRONTEND_DIR/dist" ]; then
    echo "  [前端编译] 正在使用 Vite 编译 React 静态资源..."
    (cd "$FRONTEND_DIR" && pnpm build > /dev/null 2>&1 || true)
fi

FRONTEND_SERVE_DIR="$FRONTEND_DIR/dist"
if [ ! -d "$FRONTEND_SERVE_DIR" ]; then
    FRONTEND_SERVE_DIR="$FRONTEND_DIR"
fi

echo "[2/2] 正在启动前端 React 控制台服务 (Port: 3000)..."
python3 -m http.server 3000 --directory "$FRONTEND_SERVE_DIR" > /dev/null 2>&1 &
FRONTEND_PID=$!

echo "============================================================"
echo "服务已全部就绪！"
echo "前端 Web 页面 : http://127.0.0.1:3000"
echo "后端 API 文档 : http://127.0.0.1:8000/docs"
echo "健康检查接口  : http://127.0.0.1:8000/api/health"
echo "============================================================"
echo "按 Ctrl+C 即可同时停止前后端服务..."

# 捕获退出信号，优雅杀掉子进程
cleanup() {
    echo ""
    echo "正在关闭前后端服务..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo "服务已全部停止。"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 等待后台进程
wait
