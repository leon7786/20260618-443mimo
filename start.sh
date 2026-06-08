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
TPROXY_SCRIPT="${APP_DIR}/tproxy.sh"
CERT_FILE="${APP_DIR}/certs/server.crt"
KEY_FILE="${APP_DIR}/certs/server.key"

[ "$(id -u)" -ne 0 ] && { echo "[ERROR] 需要 root 权限: sudo bash $0" >&2; exit 1; }

# ── helpers ──────────────────────────────────────────────
detect_iptables() {
  if command -v iptables-legacy >/dev/null 2>&1; then echo "iptables-legacy"
  elif command -v iptables >/dev/null 2>&1; then echo "iptables"
  else echo ""; fi
}

port_listening() {
  local port="$1"
  ss -lnt 2>/dev/null | grep -q ":${port}\b" && return 0
  netstat -lnt 2>/dev/null | grep -q ":${port}\b" && return 0
  return 1
}

ensure_dirs() {
  mkdir -p "${APP_DIR}"/{ruleset,certs,console}
}

# ── dependency check ─────────────────────────────────────
ensure_tools() {
  local missing=() pkgmap=()
  command -v curl     >/dev/null 2>&1 || { missing+=(curl);     pkgmap+=(curl); }
  command -v openssl  >/dev/null 2>&1 || { missing+=(openssl);  pkgmap+=(openssl); }
  command -v python3  >/dev/null 2>&1 || { missing+=(python3);  pkgmap+=(python3); }
  python3 -c 'import yaml' 2>/dev/null || { missing+=(python3-yaml); pkgmap+=(python3-yaml); }
  command -v iptables >/dev/null 2>&1 || { missing+=(iptables); pkgmap+=(iptables); }
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
    x86_64|amd64)   echo "${APP_DIR}/mimo-linux-amd64" ;;
    aarch64|arm64)  echo "${APP_DIR}/mimo-linux-arm64-a53" ;;
    armv7l|armv7*)  echo "${APP_DIR}/mimo-linux-armv7-router" ;;
    *) echo "[ERROR] 不支持架构: $(uname -m)" >&2; exit 1 ;;
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
  default-nameserver: [180.76.76.76, 119.29.29.29]
  nameserver: [https://dns.alidns.com/dns-query, https://doh.pub/dns-query]
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
  [ -f "${AUTH_FILE}" ] && return
  echo "[AUTH] 生成默认账号 admin12 / admin12"
  export AUTH_FILE CONSOLE_DIR="${APP_DIR}/console"
  python3 - <<'PY'
import base64, hashlib, os, yaml
path = os.environ["AUTH_FILE"]
salt = os.urandom(16)
digest = hashlib.pbkdf2_hmac("sha256", b"admin12", salt, 200000)
data = {"username":"admin12","algorithm":"pbkdf2_sha256","iterations":200000,
        "salt":base64.b64encode(salt).decode(),"hash":base64.b64encode(digest).decode()}
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path,"w",encoding="utf-8") as f:
    yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
os.chmod(path, 0o600)
print(f"  用户名: admin12  密码: admin12")
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
ExecStart=${TPROXY_SCRIPT} start
ExecStop=${TPROXY_SCRIPT} stop

[Install]
WantedBy=multi-user.target
TSVCEOF

  systemctl daemon-reload
}

# ── tproxy script ─────────────────────────────────────────
write_tproxy_script() {
  local IPT; IPT="$(detect_iptables)"
  [ -z "${IPT}" ] && { echo "[ERROR] iptables 不可用" >&2; exit 1; }

  cat > "${TPROXY_SCRIPT}" <<TPROXYEOF
#!/usr/bin/env bash
set -euo pipefail

REDIR_PORT=7892
DNS_PORT=1053
FWMARK=255
IPT="${IPT}"

# dynamic bypass ports — override via env if needed
: "\${MIMO_BYPASS_PORTS:=2000,19093,7892,1053}"

case "\${1:-}" in
start)
    # cleanup (idempotent)
    for chain in OUTPUT PREROUTING; do
      \$IPT -t nat -D \$chain -p tcp -j MIMO_REDIR 2>/dev/null || true
      \$IPT -t nat -D \$chain -p udp --dport 53 -j MIMO_REDIR 2>/dev/null || true
    done
    \$IPT -t nat -F MIMO_REDIR 2>/dev/null || true
    \$IPT -t nat -X MIMO_REDIR 2>/dev/null || true

    \$IPT -t nat -N MIMO_REDIR
    \$IPT -t nat -A MIMO_REDIR -m mark --mark \$FWMARK -j RETURN
    \$IPT -t nat -A MIMO_REDIR -p tcp -m multiport --dports "\$MIMO_BYPASS_PORTS" -j RETURN
    \$IPT -t nat -A MIMO_REDIR -p udp -m multiport --dports "\$MIMO_BYPASS_PORTS" -j RETURN
    # DNS 劫持 → Mihomo DNS (必须在私有 IP RETURN 之前: 内网 DNS 如 WSL 172.30.x 的 :53 查询否则会被绕过 → DNS 污染)
    \$IPT -t nat -A MIMO_REDIR -p tcp --dport 53 -j REDIRECT --to-ports \$DNS_PORT
    \$IPT -t nat -A MIMO_REDIR -p udp --dport 53 -j REDIRECT --to-ports \$DNS_PORT
    for ip in 127.0.0.0/8 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10 224.0.0.0/4 240.0.0.0/4; do
      \$IPT -t nat -A MIMO_REDIR -d "\$ip" -j RETURN
    done
    # 云厂商内网: metadata / 本机公网 IP
    \$IPT -t nat -A MIMO_REDIR -d 169.254.0.23 -j RETURN 2>/dev/null || true
    \$IPT -t nat -A MIMO_REDIR -d 100.100.100.200 -j RETURN 2>/dev/null || true
    PUB_IP=\$(curl -fsSL --max-time 3 ifconfig.me 2>/dev/null || true)
    [ -n "\$PUB_IP" ] && \$IPT -t nat -A MIMO_REDIR -d "\$PUB_IP" -j RETURN 2>/dev/null || true
    \$IPT -t nat -A MIMO_REDIR -p tcp -j REDIRECT --to-ports \$REDIR_PORT

    \$IPT -t nat -I OUTPUT -p tcp -j MIMO_REDIR
    \$IPT -t nat -I OUTPUT -p udp --dport 53 -j MIMO_REDIR
    \$IPT -t nat -I PREROUTING -p tcp -j MIMO_REDIR
    \$IPT -t nat -I PREROUTING -p udp --dport 53 -j MIMO_REDIR

    # QUIC block (force TCP fallback)
    \$IPT -D INPUT -p udp --dport 443 -j REJECT 2>/dev/null || true
    \$IPT -I INPUT -p udp --dport 443 -j REJECT --reject-with icmp-port-unreachable

    echo "透明代理已启动"
    ;;

stop)
    for chain in OUTPUT PREROUTING; do
      \$IPT -t nat -D \$chain -p tcp -j MIMO_REDIR 2>/dev/null || true
      \$IPT -t nat -D \$chain -p udp --dport 53 -j MIMO_REDIR 2>/dev/null || true
    done
    \$IPT -t nat -F MIMO_REDIR 2>/dev/null || true
    \$IPT -t nat -X MIMO_REDIR 2>/dev/null || true
    \$IPT -D INPUT -p udp --dport 443 -j REJECT 2>/dev/null || true
    echo "透明代理已停止"
    ;;

status)
    echo "=== MIMO_REDIR ==="; \$IPT -t nat -L MIMO_REDIR -n -v 2>/dev/null || echo "(空)"
    echo "=== OUTPUT ==="; \$IPT -t nat -L OUTPUT -n -v 2>/dev/null | grep -i mimo || echo "(无)"
    ;;
*)  echo "用法: \$0 {start|stop|status}"; exit 1 ;;
esac
TPROXYEOF
  chmod +x "${TPROXY_SCRIPT}"
}

# ── healthcheck ───────────────────────────────────────────
write_healthcheck() {
  cat > "${APP_DIR}/healthcheck.sh" <<'HCEOF'
#!/usr/bin/env bash
check() {
  local target="https://www.google.com/generate_204"
  if curl -fsSL --max-time 5 -o /dev/null "$target" 2>/dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') Google OK"; return 0
  fi
  echo "$(date '+%Y-%m-%d %H:%M:%S') Google FAIL — 切换到直连模式"
  # could auto-revert tproxy here if desired
  return 1
}
case "${1:-}" in check) check ;; *) echo "usage: $0 check" ;; esac
HCEOF
  chmod +x "${APP_DIR}/healthcheck.sh"

  cat > /etc/systemd/system/mimo-healthcheck.service <<HCSVC
[Unit]
Description=mimo health check
After=${SERVICE_NAME}
[Service]
Type=oneshot
ExecStart=${APP_DIR}/healthcheck.sh check
HCSVC

  cat > /etc/systemd/system/mimo-healthcheck.timer <<HCTMR
[Unit]
Description=mimo health check timer
[Timer]
OnBootSec=60
OnUnitActiveSec=300
RandomSec=30
[Install]
WantedBy=timers.target
HCTMR
  systemctl daemon-reload
  systemctl enable --now mimo-healthcheck.timer 2>/dev/null || true
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
  write_tproxy_script
  write_services
  write_healthcheck

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
  echo "  账号: admin12  密码: admin12"
  echo "============================================"
  echo ""
  echo "  启用透明代理: 控制台 → 勾选 VPS透明代理 + 配置链式代理 → 应用"
  echo "  管理: bash ${APP_DIR}/start.sh"
  echo ""
}

uninstall() {
  echo "[WARN] 将停止所有服务并删除配置"
  read -r -p "确认? 输入 YES 继续: " confirm
  [ "${confirm}" != "YES" ] && { echo "已取消"; return; }
  for svc in mimo-tproxy mimo-console mimo-healthcheck.timer mimo; do
    systemctl disable --now "${svc}" 2>/dev/null || true
  done
  bash "${TPROXY_SCRIPT}" stop 2>/dev/null || true
  rm -f "${SERVICE_FILE}" "${CONSOLE_SERVICE}" "${TPROXY_SERVICE}"
  rm -f /etc/systemd/system/mimo-healthcheck.{service,timer}
  systemctl daemon-reload
  find "${APP_DIR}" -mindepth 1 -maxdepth 1 ! -name 'start.sh' -exec rm -rf {} + 2>/dev/null
  echo "已卸载。"
}

status() {
  local s c t h
  s="$(systemctl is-active "${SERVICE_NAME}" 2>/dev/null || echo down)"
  c="$(systemctl is-active "${CONSOLE_SERVICE_NAME}" 2>/dev/null || echo down)"
  t="$(systemctl is-active "${TPROXY_SERVICE_NAME}" 2>/dev/null || echo down)"
  h="$(systemctl is-active mimo-healthcheck.timer 2>/dev/null || echo down)"

  echo "mimo:       ${s}  (PID $(systemctl show -p MainPID --value "${SERVICE_NAME}" 2>/dev/null || echo ?))"
  echo "console:    ${c}  :2000 $(port_listening 2000 && echo '✓' || echo '✗')"
  echo "tproxy:     ${t}  :7892 $(port_listening 7892 && echo '✓' || echo '✗')  DNS:1053 $(port_listening 1053 && echo '✓' || echo '✗')"
  echo "health:     ${h}"
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
  uninstall) uninstall ;;
  *)
    echo "mimo 管理脚本"
    echo "用法: bash $0 {install|start|stop|restart|status|uninstall}"
    echo ""
    echo "  install   — 全新安装 (幂等)"
    echo "  status    — 查看状态"
    echo "  uninstall — 完全卸载"
    exit 0
    ;;
esac
