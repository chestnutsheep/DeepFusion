#!/bin/bash
# DeepFusion 一键重启：杀掉旧的 后端(5173) + 前端(8080)，后台常驻拉起。
# 用法：bash restart_all.sh
# 说明：用 nohup 后台运行，日志写 logs/backend.log / logs/frontend.log，进程不随本脚本退出而终止。

BASE_DIR="/home/AI/workspace/Mcp Server/DeepFusion"
FRONTEND_DIR="$BASE_DIR/dashboard"
LOG_DIR="$BASE_DIR/logs"
mkdir -p "$LOG_DIR"

echo "=== DeepFusion 重启 ==="

# 1. 杀掉占用 5173 / 8080 的进程
for port in 5173 8080; do
  pid=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K\d+' | head -1 || true)
  if [ -n "$pid" ]; then
    echo "  关闭端口 $port (PID: $pid)"
    kill "$pid" 2>/dev/null || true
  fi
done
# 兜底：直接按命令名杀
pkill -f "serve.py" 2>/dev/null || true
pkill -f "vite --host" 2>/dev/null || true
sleep 1

# 2. 启动后端（nohup 常驻）
cd "$BASE_DIR"
nohup .venv/bin/python serve.py > "$LOG_DIR/backend.log" 2>&1 &
echo "  后端已拉起 (日志: $LOG_DIR/backend.log)"

# 3. 等后端就绪
for i in $(seq 1 30); do
  sleep 2
  resp=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/api/tools/list 2>/dev/null)
  if [ "$resp" = "200" ]; then
    echo "  后端就绪 (http://localhost:5173)"
    break
  fi
done

# 4. 启动前端（nohup 常驻 + 健康检查 + 重试）
# 前端的 vite 文件监视器偶发 EMFILE(inotify 耗尽) 会直接崩溃导致 8080 起不来，
# 因此加就绪探测与重试，避免“点图标后看板用不了”。
cd "$FRONTEND_DIR"
MAX_TRIES=3
for try in $(seq 1 $MAX_TRIES); do
  # 启动前先清掉可能残留的 vite 进程
  pkill -f "vite --host 0.0.0.0 --port 8080" 2>/dev/null || true
  sleep 1
  nohup npx vite --host 0.0.0.0 --port 8080 > "$LOG_DIR/frontend.log" 2>&1 &
  echo "  前端尝试启动 (第 $try/$MAX_TRIES 次, 日志: $LOG_DIR/frontend.log)"
  up=0
  for i in $(seq 1 15); do
    sleep 2
    resp=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null)
    if [ "$resp" = "200" ]; then
      up=1
      break
    fi
  done
  if [ "$up" = "1" ]; then
    echo "  前端就绪 (http://localhost:8080)"
    break
  else
    echo "  前端第 $try 次未就绪，查看日志:"
    tail -n 8 "$LOG_DIR/frontend.log" 2>/dev/null
  fi
done
if [ "$up" != "1" ]; then
  echo "  [警告] 前端多次启动失败，请检查 $LOG_DIR/frontend.log"
fi

echo "=== 完成 ==="
echo "  前端 UI: http://localhost:8080/"
echo "  后端 API: http://localhost:5173/api/tools/call"
echo "  查看日志: tail -f $LOG_DIR/backend.log / $LOG_DIR/frontend.log"
