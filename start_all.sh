#!/bin/bash
# DeepFusion 一键启动脚本 v2
# 后端 API → :5173  前端 UI → :8080
# 按回车键关闭所有服务并退出

BASE_DIR="/home/AI/workspace/Mcp Server/DeepFusion"
FRONTEND_DIR="$BASE_DIR/dashboard"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "正在关闭服务..."
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
  wait 2>/dev/null
  echo "✅ 已关闭。"
  exit 0
}

trap cleanup SIGINT SIGTERM

echo "================================================"
echo "  DeepFusion — 启动中..."
echo "  后端 API: http://localhost:5173/api/tools/call"
echo "  前端 UI:  http://localhost:8080/"
echo "================================================"
echo ""

# 清理占用端口
for port in 5173 8080; do
  pid=$(ss -tlnp | grep ":$port " | grep -oP 'pid=\K\d+' || true)
  if [ -n "$pid" ]; then
    echo "  清理端口 $port (PID: $pid)"
    kill "$pid" 2>/dev/null || true
  fi
done
sleep 1

# 启动后端（纯 API，不服务前端页面）
cd "$BASE_DIR"
.venv/bin/python serve.py &

BACKEND_PID=$!
echo "✅ 后端已启动 (PID: $BACKEND_PID)"

# 等待后端就绪
for i in $(seq 1 30); do
  sleep 2
  resp=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/api/tools/list 2>/dev/null)
  if [ "$resp" = "200" ]; then
    echo "  后端就绪"
    break
  fi
done

# 启动前端（Vite 开发服务器）
cd "$FRONTEND_DIR"
npx vite --host 0.0.0.0 &
FRONTEND_PID=$!
echo "✅ 前端已启动 (PID: $FRONTEND_PID)"

echo ""
echo "================================================"
echo "  ✅ 全部就绪"
echo "  打开浏览器访问: http://localhost:8080/"
echo ""
echo "  按回车键关闭所有服务并退出"
echo "================================================"

read -r
cleanup