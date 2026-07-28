#!/usr/bin/env bash
# mimo 透明代理 — iptables 版（兼容旧系统 nftables < 1.0）
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_FILE="${APP_DIR}/config.yaml"
REDIR_PORT=7892
DNS_PORT=1053
FWMARK=255

# 从 config.yaml 提取 bypass 端口
get_bypass_ports() {
  local ports="2000,2001,2002,19093,7892,1053,22"
  if command -v python3 &>/dev/null && [ -f "$CONFIG_FILE" ]; then
    ports=$(python3 - "$CONFIG_FILE" <<'PY'
import sys, yaml
ports = {2000, 2001, 19093, 7892, 1053, 22}
try:
    c = yaml.safe_load(open(sys.argv[1])) or {}
    for l in c.get("listeners") or []:
        if isinstance(l, dict) and l.get("port"):
            ports.add(int(l["port"]))
    dns = str((c.get("dns") or {}).get("listen", ""))
    if ":" in dns and dns.rsplit(":", 1)[-1].isdigit():
        ports.add(int(dns.rsplit(":", 1)[-1]))
    ec = str(c.get("external-controller", ""))
    if ":" in ec and ec.rsplit(":", 1)[-1].isdigit():
        ports.add(int(ec.rsplit(":", 1)[-1]))
    if c.get("redir-port"):
        ports.add(int(c["redir-port"]))
except Exception:
    pass
print(",".join(str(p) for p in sorted(ports)))
PY
    ) || ports="22,1053,2000,2001,7892,19093"
  fi
  echo "$ports"
}

get_public_ip() {
  curl -fsSL --max-time 3 ifconfig.me 2>/dev/null || true
}

start() {
  local MIMO_PORTS; MIMO_PORTS="$(get_bypass_ports)"

  # 清理旧规则（幂等）
  iptables -t nat -D OUTPUT -p tcp -j MIMO_REDIR 2>/dev/null || true
  iptables -t nat -D OUTPUT -p udp --dport 53 -j MIMO_REDIR 2>/dev/null || true
  iptables -t nat -D PREROUTING -p tcp -j MIMO_REDIR 2>/dev/null || true
  iptables -t nat -D PREROUTING -p udp --dport 53 -j MIMO_REDIR 2>/dev/null || true
  iptables -t nat -F MIMO_REDIR 2>/dev/null || true
  iptables -t nat -X MIMO_REDIR 2>/dev/null || true

  # 创建自定义链
  iptables -t nat -N MIMO_REDIR

  # 防回环：跳过 mimo 自身出站流量
  iptables -t nat -A MIMO_REDIR -m mark --mark $FWMARK -j RETURN
  # 跳过 mimo 相关端口
  iptables -t nat -A MIMO_REDIR -p tcp -m multiport --dports "$MIMO_PORTS" -j RETURN
  iptables -t nat -A MIMO_REDIR -p udp -m multiport --dports "$MIMO_PORTS" -j RETURN
  # 跳过保留地址
  for ip in 127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10 224.0.0.0/4 240.0.0.0/4; do
    iptables -t nat -A MIMO_REDIR -d "$ip" -j RETURN
  done
  # 本机公网IP绕过
  local PUB; PUB="$(get_public_ip)"
  if [ -n "$PUB" ] && echo "$PUB" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    iptables -t nat -A MIMO_REDIR -d "$PUB" -j RETURN
  fi

  # DNS 重定向（放 TCP 前面）
  iptables -t nat -A MIMO_REDIR -p tcp --dport 53 -j REDIRECT --to-ports "$DNS_PORT"
  iptables -t nat -A MIMO_REDIR -p udp --dport 53 -j REDIRECT --to-ports "$DNS_PORT"
  # TCP 重定向
  iptables -t nat -A MIMO_REDIR -p tcp -j REDIRECT --to-ports "$REDIR_PORT"

  # 挂载到 PREROUTING 和 OUTPUT
  iptables -t nat -A PREROUTING -p udp --dport 53 -j MIMO_REDIR
  iptables -t nat -A PREROUTING -p tcp -j MIMO_REDIR
  iptables -t nat -A OUTPUT -p udp --dport 53 -j MIMO_REDIR
  iptables -t nat -A OUTPUT -p tcp -j MIMO_REDIR

  # QUIC 阻断（强制走 TCP 代理）
  iptables -t filter -D INPUT -p udp --dport 443 -j REJECT --reject-with icmp-port-unreachable 2>/dev/null || true
  iptables -t filter -A INPUT -p udp --dport 443 -j REJECT --reject-with icmp-port-unreachable

  echo "透明代理已启动 (iptables, bypass ports: ${MIMO_PORTS})"
}

stop() {
  iptables -t nat -D OUTPUT -p tcp -j MIMO_REDIR 2>/dev/null || true
  iptables -t nat -D OUTPUT -p udp --dport 53 -j MIMO_REDIR 2>/dev/null || true
  iptables -t nat -D PREROUTING -p tcp -j MIMO_REDIR 2>/dev/null || true
  iptables -t nat -D PREROUTING -p udp --dport 53 -j MIMO_REDIR 2>/dev/null || true
  iptables -t nat -F MIMO_REDIR 2>/dev/null || true
  iptables -t nat -X MIMO_REDIR 2>/dev/null || true
  iptables -t filter -D INPUT -p udp --dport 443 -j REJECT --reject-with icmp-port-unreachable 2>/dev/null || true
  echo "透明代理已停止 (iptables)"
}

status() {
  echo "=== iptables MIMO_REDIR ==="
  iptables -t nat -L MIMO_REDIR -n --line-numbers 2>/dev/null || echo "(无)"
  echo ""
  echo "=== QUIC block ==="
  iptables -t filter -L INPUT -n 2>/dev/null | grep -i "udp.*443" || echo "(无)"
}

case "${1:-}" in
  start)  start ;;
  stop)   stop ;;
  status) status ;;
  *)
    echo "用法: bash $0 {start|stop|status}"
    exit 1
    ;;
esac
