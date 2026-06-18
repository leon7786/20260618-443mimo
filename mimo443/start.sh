#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="mimo.service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"
CONSOLE_SERVICE_NAME="mimo-console.service"
CONSOLE_SERVICE="/etc/systemd/system/${CONSOLE_SERVICE_NAME}"
TPROXY_SERVICE_NAME="mimo-tproxy.service"
TPROXY_SERVICE="/etc/systemd/system/${TPROXY_SERVICE_NAME}"
CONSOLE_PY="${APP_DIR}/console/console.py"
AUTH_FILE="${APP_DIR}/console/console-auth.yaml"
CONFIG_FILE="${APP_DIR}/config.yaml"
CERT_FILE="${APP_DIR}/ruleset/server.crt"
KEY_FILE="${APP_DIR}/ruleset/server.key"

[ "$(id -u)" -ne 0 ] && { echo "[ERROR] 需要 root 权限: sudo bash $0" >&2; exit 1; }

# ── helpers ──────────────────────────────────────────────
port_listening() {
  local port="$1"
  ss -lnt 2>/dev/null | grep -q ":${port}\b" && return 0
  netstat -lnt 2>/dev/null | grep -q ":${port}\b" && return 0
  return 1
}

ensure_dirs() {
  mkdir -p "${APP_DIR}"/{ruleset,console}
}

# ── dependency check ─────────────────────────────────────
ensure_tools() {
  local missing=() pkgmap=()
  command -v curl     >/dev/null 2>&1 || { missing+=(curl);     pkgmap+=(curl); }
  command -v openssl  >/dev/null 2>&1 || { missing+=(openssl);  pkgmap+=(openssl); }
  command -v python3  >/dev/null 2>&1 || { missing+=(python3);  pkgmap+=(python3); }
  python3 -c 'import yaml' 2>/dev/null || { missing+=(python3-yaml); pkgmap+=(python3-yaml); }
  command -v nft      >/dev/null 2>&1 || { missing+=(nftables); pkgmap+=(nftables); }
  command -v ss       >/dev/null 2>&1 || command -v netstat >/dev/null 2>&1 || { missing+=(iproute2); pkgmap+=(iproute2); }
  command -v dig      >/dev/null 2>&1 || { missing+=(dnsutils); pkgmap+=(dnsutils); }
  [ "${#missing[@]}" -eq 0 ] && return
  echo "[DEPS] 安装: ${missing[*]}"
  apt-get update -qq 2>/dev/null
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ca-certificates "${pkgmap[@]}" 2>/dev/null && return
  # fallback: try yum
  yum install -y -q "${pkgmap[@]}" 2>/dev/null && return
  echo "[WARN] 自动安装依赖失败, 请手动安装: ${missing[*]}" >&2
}

# ── certs ─────────────────────────────────────────────────
ensure_certs() {
  [ -f "${CERT_FILE}" ] && [ -f "${KEY_FILE}" ] && return
  echo "[CERTS] 生成自签名证书..."
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "${KEY_FILE}" -out "${CERT_FILE}" -days 3650 \
    -subj "/CN=mimo-local" 2>/dev/null
  chmod 600 "${KEY_FILE}" "${CERT_FILE}"
}

# ── binary ────────────────────────────────────────────────
select_binary() {
  case "$(uname -m)" in
    x86_64|amd64) echo "${APP_DIR}/mimo-linux-amd64" ;;
    *)            echo "${APP_DIR}/mimo-linux-arm64-a53" ;;
  esac
}

ensure_binary() {
  local bin; bin="$(select_binary)"
  [ -f "${bin}" ] || { echo "[ERROR] 缺少内核: ${bin}" >&2; exit 1; }
  chmod +x "${bin}"
  echo "[CORE] ${bin}"
}

# ── defaults ──────────────────────────────────────────────
write_default_config() {
  [ -f "${CONFIG_FILE}" ] && return
  echo "[CONFIG] 生成默认配置..."
  cat > "${CONFIG_FILE}" <<'EOF'
allow-lan: false
mode: rule
log-level: info
ipv6: false
tcp-concurrent: true
unified-delay: true
connection-timeout: 5
keep-alive-interval: 30
keep-alive-idle: 600
external-controller: 127.0.0.1:19093
geodata-mode: false
dns:
  enable: true
  listen: 0.0.0.0:1053
  ipv6: false
  enhanced-mode: redir-host
  respect-rules: true
  default-nameserver: [223.5.5.5, 180.76.76.76, 119.29.29.29]
  proxy-server-nameserver: [223.5.5.5, 180.76.76.76, 119.29.29.29]
  nameserver: [https://cloudflare-dns.com/dns-query, https://dns.google/dns-query]
listeners: []
rules:
- IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
- IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
- IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
- IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
- MATCH,DIRECT
proxy-groups:
- name: 节点选择
  type: select
  proxies: [DIRECT]
EOF
  chmod 600 "${CONFIG_FILE}"
}

# ── console auth ──────────────────────────────────────────
ensure_console_auth() {
  local pass="${MIMO_UUID:-}"
  if [ -z "${pass}" ]; then
    pass="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())')"
  fi
  # persist UUID always (reinstall-safe)
  echo "${pass}" > "${APP_DIR}/uuid"
  chmod 600 "${APP_DIR}/uuid"
  # generate auth only if not present
  if [ -f "${AUTH_FILE}" ]; then
    echo "[AUTH] 已有认证文件，跳过。密码见 ${APP_DIR}/uuid"
    return
  fi
  echo "[AUTH] user: admin12  pass: ${pass}"
  export AUTH_FILE CONSOLE_DIR="${APP_DIR}/console" AUTH_PASS="${pass}"
  python3 - <<'PY'
import base64, hashlib, os, yaml
path = os.environ["AUTH_FILE"]
salt = os.urandom(16)
digest = hashlib.pbkdf2_hmac("sha256", os.environ["AUTH_PASS"].encode(), salt, 200000)
data = {"username":"admin12","algorithm":"pbkdf2_sha256","iterations":200000,
        "salt":base64.b64encode(salt).decode(),"hash":base64.b64encode(digest).decode()}
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path,"w",encoding="utf-8") as f:
    yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
os.chmod(path, 0o600)
print(f"  user: admin12  pass: {os.environ['AUTH_PASS']}")
PY
}

# ── systemd services ──────────────────────────────────────
write_services() {
  local bin; bin="$(select_binary)"

  cat > "${SERVICE_FILE}" <<SVCEOF
[Unit]
Description=mimo service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
ExecStart=${bin} -d ${APP_DIR} -f ${CONFIG_FILE}
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=3
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
SVCEOF

  cat > "${CONSOLE_SERVICE}" <<CSVCEOF
[Unit]
Description=mimo console
After=network-online.target ${SERVICE_NAME}
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
Environment=APP_DIR=${APP_DIR}
Environment=CONSOLE_HOST=0.0.0.0
Environment=CONSOLE_PORT=2000
Environment=MIMO_SERVICE_NAME=${SERVICE_NAME}
Environment=MIMO_BINARY=${bin}
ExecStart=/usr/bin/python3 -B ${CONSOLE_PY}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
CSVCEOF

  cat > "${TPROXY_SERVICE}" <<TSVCEOF
[Unit]
Description=mimo transparent proxy
After=network.target ${SERVICE_NAME}
Requires=${SERVICE_NAME}

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=${APP_DIR}/start.sh tproxy-start
ExecStop=${APP_DIR}/start.sh tproxy-stop

[Install]
WantedBy=multi-user.target
TSVCEOF

  systemctl daemon-reload
}

# ── tproxy runtime (nftables) ─────────────────────────────
# bypass ports derived from config.yaml (listeners/dns/controller/redir) + 服务端口 + SSH
tproxy_bypass_elements() {
  python3 - "$CONFIG_FILE" <<'PY'
import sys, yaml
ports = {2000, 19093, 7892, 1053, 22}
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
# SSH 端口段 60000-60050 始终绕过
print(", ".join(str(p) for p in sorted(ports)) + ", 60000-60050")
PY
}

run_tproxy_start() {
  command -v nft >/dev/null 2>&1 || { echo "[ERROR] nft 不可用" >&2; exit 1; }
  local REDIR_PORT=7892 DNS_PORT=1053 FWMARK=0xff
  local BYPASS; BYPASS="$(tproxy_bypass_elements 2>/dev/null)"
  [ -z "${BYPASS}" ] && BYPASS="22, 1053, 2000, 7892, 19093, 60000-60050"
  # 本机公网 IP 绕过 (防自连/防 SSH 入站被劫持)
  local PUB PUB_RULE=""
  PUB=$(curl -fsSL --max-time 3 ifconfig.me 2>/dev/null || true)
  if [ -n "${PUB}" ] && echo "${PUB}" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    PUB_RULE="ip daddr ${PUB} return"
  fi
  nft -f - <<EOF
add table ip mimo_tproxy
delete table ip mimo_tproxy
table ip mimo_tproxy {
  set bypass {
    type inet_service
    flags interval
    elements = { ${BYPASS} }
  }
  set reserved {
    type ipv4_addr
    flags interval
    elements = { 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16,
                 169.254.0.0/16, 100.64.0.0/10, 224.0.0.0/4, 240.0.0.0/4 }
  }
  chain prerouting {
    type nat hook prerouting priority -100; policy accept;
    meta mark ${FWMARK} return
    meta l4proto { tcp, udp } th dport 53 redirect to :${DNS_PORT}
    ip daddr @reserved return
    ${PUB_RULE}
    tcp dport @bypass return
    udp dport @bypass return
    meta l4proto tcp redirect to :${REDIR_PORT}
  }
  chain output {
    type nat hook output priority 100; policy accept;
    meta mark ${FWMARK} return
    meta l4proto { tcp, udp } th dport 53 redirect to :${DNS_PORT}
    ip daddr @reserved return
    ${PUB_RULE}
    tcp dport @bypass return
    udp dport @bypass return
    meta l4proto tcp redirect to :${REDIR_PORT}
  }
}
add table ip mimo_quic
delete table ip mimo_quic
table ip mimo_quic {
  chain input {
    type filter hook input priority 0; policy accept;
    udp dport 443 reject with icmp type port-unreachable
  }
}
EOF
  echo "透明代理已启动 (nft, bypass: ${BYPASS})"
}
run_tproxy_stop() {
  command -v nft >/dev/null 2>&1 || { echo "[ERROR] nft 不可用" >&2; exit 1; }
  nft delete table ip mimo_tproxy 2>/dev/null || true
  nft delete table ip mimo_quic 2>/dev/null || true
  echo "透明代理已停止"
}
run_tproxy_status() {
  command -v nft >/dev/null 2>&1 || { echo "[ERROR] nft 不可用" >&2; exit 1; }
  echo "=== mimo_tproxy ==="; nft list table ip mimo_tproxy 2>/dev/null || echo "(无)"
  echo "=== mimo_quic ===";   nft list table ip mimo_quic 2>/dev/null || echo "(无)"
}

# ── stop systemd-resolved ─────────────────────────────────
stop_resolved() {
  systemctl is-active --quiet systemd-resolved 2>/dev/null || return 0
  echo "[DNS] 停止 systemd-resolved (端口冲突)..."
  systemctl disable --now systemd-resolved 2>/dev/null || true
  if [ -L /etc/resolv.conf ]; then
    rm -f /etc/resolv.conf
    echo "nameserver 119.29.29.29" > /etc/resolv.conf
    echo "nameserver 180.76.76.76" >> /etc/resolv.conf
  fi
}

# ── main actions ──────────────────────────────────────────
install() {
  echo "=== mimo 安装 ==="
  ensure_dirs
  ensure_tools
  stop_resolved
  ensure_binary
  ensure_certs
  ensure_console_auth
  write_default_config
  write_services

  # validate
  echo "[VALIDATE] 校验配置..."
  "$(select_binary)" -d "${APP_DIR}" -t -f "${CONFIG_FILE}" || {
    echo "[ERROR] 配置校验失败，保留默认配置" >&2
    exit 1
  }

  # start
  echo "[START] 启动 mimo..."
  systemctl enable --now "${SERVICE_NAME}"
  echo "[WAIT] 等待端口就绪..."
  for i in $(seq 1 20); do
    port_listening 19093 && break
    sleep 1
  done
  systemctl enable --now "${CONSOLE_SERVICE_NAME}"
  echo ""
  echo "============================================"
  echo "  mimo 安装完成!"
  echo "  控制台: http://$(curl -s --max-time 2 ifconfig.me 2>/dev/null || echo '服务器IP'):2000"
  echo "  账号: admin12  密码: $(cat "${APP_DIR}/uuid" 2>/dev/null || echo '见 uuid 文件')"
  echo "============================================"
  echo ""
  echo "  透明代理: systemctl enable --now ${TPROXY_SERVICE_NAME}"
  echo "  管理: bash ${APP_DIR}/start.sh"
  echo ""
}

uninstall() {
  echo "[WARN] 将停止所有服务并删除配置"
  read -r -p "确认? 输入 YES 继续: " confirm
  [ "${confirm}" != "YES" ] && { echo "已取消"; return; }
  for svc in mimo-tproxy mimo-console mimo; do
    systemctl disable --now "${svc}" 2>/dev/null || true
  done
  rm -f "${SERVICE_FILE}" "${CONSOLE_SERVICE}" "${TPROXY_SERVICE}"
  systemctl daemon-reload
  find "${APP_DIR}" -mindepth 1 -maxdepth 1 ! -name 'start.sh' -exec rm -rf {} + 2>/dev/null
  echo "已卸载。"
}

status() {
  local s c t
  s="$(systemctl is-active "${SERVICE_NAME}" 2>/dev/null || echo down)"
  c="$(systemctl is-active "${CONSOLE_SERVICE_NAME}" 2>/dev/null || echo down)"
  t="$(systemctl is-active "${TPROXY_SERVICE_NAME}" 2>/dev/null || echo down)"

  echo "mimo:       ${s}  (PID $(systemctl show -p MainPID --value "${SERVICE_NAME}" 2>/dev/null || echo ?))"
  echo "console:    ${c}  :2000 $(port_listening 2000 && echo '✓' || echo '✗')"
  echo "tproxy:     ${t}  :7892 $(port_listening 7892 && echo '✓' || echo '✗')  DNS:1053 $(port_listening 1053 && echo '✓' || echo '✗')"
  echo "controller: :19093 $(port_listening 19093 && echo '✓' || echo '✗')"
  echo "binary:     $(select_binary 2>/dev/null || echo '?')"
  echo "config:     ${CONFIG_FILE}"
  echo "access:     http://服务器IP:2000"
}

# ── dispatch ──────────────────────────────────────────────
case "${1:-}" in
  install)   install ;;
  start)     systemctl start "${SERVICE_NAME}" ;;
  stop)      systemctl stop "${SERVICE_NAME}" ;;
  restart)   systemctl restart "${SERVICE_NAME}" ;;
  status)    status ;;
  tproxy-start)  run_tproxy_start ;;
  tproxy-stop)   run_tproxy_stop ;;
  tproxy-status) run_tproxy_status ;;
  uninstall)     uninstall ;;
  *)
    echo "mimo 管理脚本"
    echo "用法: bash $0 {install|start|stop|restart|status|uninstall|tproxy-start|tproxy-stop}"
    echo ""
    echo "  install   — 全新安装 (幂等)"
    echo "  status    — 查看状态"
    echo "  uninstall — 完全卸载"
    exit 0
    ;;
esac
