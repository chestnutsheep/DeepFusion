#!/usr/bin/env bash
# 逐个切换 clash-verge 节点并测试东财 push2 连通性
set -u
SOCK=/tmp/verge/verge-mihomo.sock
GROUP="狗狗加速.com"
PUSH2="https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=1"
API="http://127.0.0.1:9097"

# 取组内所有节点名（JSON 数组 -> 一行一个，去掉引号）
mapfile -t NODES < <(curl -s --unix-socket "$SOCK" "$API/proxies/$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$GROUP")" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('\n'.join(d.get('all',[])))")

echo "共 ${#NODES[@]} 个节点，开始测 push2 ..."
FOUND=()
for n in "${NODES[@]}"; do
  enc=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$n")
  # 切换节点
  curl -s --unix-socket "$SOCK" -X PUT "$API/proxies/$GROUP" -H "Content-Type: application/json" \
    -d "$(python3 -c "import json,sys;print(json.dumps({'name':sys.argv[1]}))" "$n")" >/dev/null 2>&1
  # 等 150ms 让连接生效
  sleep 0.15
  code=$(curl -s -m 6 --unix-socket "$SOCK" -x "socks5h://127.0.0.1:7897" -o /dev/null -w "%{http_code}" "$PUSH2" 2>/dev/null)
  if [ "$code" = "200" ]; then
    echo "✅ [$code] $n"
    FOUND+=("$n")
  else
    echo "❌ [$code] $n"
  fi
done
echo
echo "=== 可用节点 (push2 返回200) ==="
if [ ${#FOUND[@]} -eq 0 ]; then
  echo "（无）所有节点均不可达 push2"
else
  printf '%s\n' "${FOUND[@]}"
  # 切回第一个可用节点
  curl -s --unix-socket "$SOCK" -X PUT "$API/proxies/$GROUP" -H "Content-Type: application/json" \
    -d "$(python3 -c "import json,sys;print(json.dumps({'name':sys.argv[1]}))" "${FOUND[0]}")" >/dev/null 2>&1
  echo "已切回: ${FOUND[0]}"
fi
