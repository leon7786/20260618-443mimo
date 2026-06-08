#!/usr/bin/env bash
set -euo pipefail

REDIR_PORT=7892
DNS_PORT=1053
FWMARK=255
IPT="iptables-legacy"

# dynamic bypass ports — override via env if needed
: "${MIMO_BYPASS_PORTS:=2000,19093,7892,1053}"

case "${1:-}" in
start)
    # cleanup (idempotent)
    for chain in OUTPUT PREROUTING; do
      $IPT -t nat -D $chain -p tcp -j MIMO_REDIR 2>/dev/null || true
      $IPT -t nat -D $chain -p udp --dport 53 -j MIMO_REDIR 2>/dev/null || true
    done
    $IPT -t nat -F MIMO_REDIR 2>/dev/null || true
    $IPT -t nat -X MIMO_REDIR 2>/dev/null || true

    $IPT -t nat -N MIMO_REDIR
    $IPT -t nat -A MIMO_REDIR -m mark --mark $FWMARK -j RETURN
    $IPT -t nat -A MIMO_REDIR -p tcp -m multiport --dports "$MIMO_BYPASS_PORTS" -j RETURN
    $IPT -t nat -A MIMO_REDIR -p udp -m multiport --dports "$MIMO_BYPASS_PORTS" -j RETURN
    # DNS 劫持 → Mihomo DNS (必须在私有 IP RETURN 之前: 内网 DNS 如 WSL 172.30.x 的 :53 查询否则会被绕过 → DNS 污染)
    $IPT -t nat -A MIMO_REDIR -p tcp --dport 53 -j REDIRECT --to-ports $DNS_PORT
    $IPT -t nat -A MIMO_REDIR -p udp --dport 53 -j REDIRECT --to-ports $DNS_PORT
    for ip in 127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10 224.0.0.0/4 240.0.0.0/4; do
      $IPT -t nat -A MIMO_REDIR -d "$ip" -j RETURN
    done
    # 云厂商内网: metadata / 本机公网 IP
    $IPT -t nat -A MIMO_REDIR -d 169.254.0.23 -j RETURN 2>/dev/null || true
    $IPT -t nat -A MIMO_REDIR -d 100.100.100.200 -j RETURN 2>/dev/null || true
    # 公网 IP 推断 (优先本地路由，避免启动阻塞)
    PUB_IP=$(ip -4 addr show | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v '^127\.' | grep -v '^10\.' | grep -v '^172\.(1[6-9]|2[0-9]|3[0-1])\.' | grep -v '^192\.168\.' | head -1)
    [ -n "$PUB_IP" ] && $IPT -t nat -A MIMO_REDIR -d "$PUB_IP" -j RETURN 2>/dev/null || true
    $IPT -t nat -A MIMO_REDIR -p tcp -j REDIRECT --to-ports $REDIR_PORT

    $IPT -t nat -I OUTPUT -p tcp -j MIMO_REDIR
    $IPT -t nat -I OUTPUT -p udp --dport 53 -j MIMO_REDIR
    $IPT -t nat -I PREROUTING -p tcp -j MIMO_REDIR
    $IPT -t nat -I PREROUTING -p udp --dport 53 -j MIMO_REDIR

    # QUIC block (force TCP fallback)
    $IPT -D INPUT -p udp --dport 443 -j REJECT 2>/dev/null || true
    $IPT -I INPUT -p udp --dport 443 -j REJECT --reject-with icmp-port-unreachable

    echo "透明代理已启动"
    ;;

stop)
    for chain in OUTPUT PREROUTING; do
      $IPT -t nat -D $chain -p tcp -j MIMO_REDIR 2>/dev/null || true
      $IPT -t nat -D $chain -p udp --dport 53 -j MIMO_REDIR 2>/dev/null || true
    done
    $IPT -t nat -F MIMO_REDIR 2>/dev/null || true
    $IPT -t nat -X MIMO_REDIR 2>/dev/null || true
    $IPT -D INPUT -p udp --dport 443 -j REJECT 2>/dev/null || true
    echo "透明代理已停止"
    ;;

status)
    echo "=== MIMO_REDIR ==="; $IPT -t nat -L MIMO_REDIR -n -v 2>/dev/null || echo "(空)"
    echo "=== OUTPUT ==="; $IPT -t nat -L OUTPUT -n -v 2>/dev/null | grep -i mimo || echo "(无)"
    ;;
*)  echo "用法: $0 {start|stop|status}"; exit 1 ;;
esac
