#!/usr/bin/env bash
# mimo 一键安装 — VPS 代理部署
# 用法: bash <(curl -fsSL https://raw.githubusercontent.com/leon7786/20260618-443mimo/master/install.sh)
#   或: MIMO_UUID=xxx MIMO_PASS=yyy bash install.sh   (非交互)
set -euo pipefail

REPO="https://github.com/leon7786/20260618-443mimo.git"
INSTALL_DIR="/root/projects/20260515-mimo443"

[ "$(id -u)" -ne 0 ] && { echo "[ERROR] need root: sudo bash install.sh" >&2; exit 1; }

# ── interactive prompts ──────────────────────────────────
if [ -z "${MIMO_UUID:-}" ]; then
  echo ""
  echo "========================================"
  echo "  mimo 安装向导"
  echo "========================================"
  read -r -p "  控制台登录密码 [admin12]: " MIMO_PASS
  read -r -p "  UUID (节点默认密码, 回车自动生成): " MIMO_UUID
  echo ""
fi

MIMO_PASS="${MIMO_PASS:-admin12}"
if [ -z "${MIMO_UUID:-}" ]; then
  MIMO_UUID="$(cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())' 2>/dev/null || echo "mimo-$(date +%s)-$$")"
fi

echo "[INFO] user: admin12  pass: ${MIMO_PASS}  uuid: ${MIMO_UUID}"
export MIMO_PASS MIMO_UUID

# ── dependencies ──────────────────────────────────────────
echo "[DEPS] 检查依赖..."
# 修复旧 Debian 失效安全源
if [ -f /etc/apt/sources.list ]; then
  sed -i 's|archive.debian.org/debian-security|archive.debian.org/debian-security|g; s|bullseye-security/updates|bullseye-security|g' /etc/apt/sources.list 2>/dev/null || true
fi
apt-get update -qq 2>/dev/null || {
  echo "[WARN] apt-get update 失败，尝试修复..."
  # 移除失效的安全源，仅保留主源
  sed -i '/security/d' /etc/apt/sources.list 2>/dev/null || true
  apt-get update -qq 2>/dev/null || true
}
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git curl ca-certificates 2>/dev/null || \
  yum install -y -q git curl ca-certificates 2>/dev/null || \
  { echo "[ERROR] git/curl 安装失败"; exit 1; }

# ── clone repo ────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "[GIT] pulling updates..."
  git -C "$INSTALL_DIR" pull --ff-only origin master 2>/dev/null || true
else
  echo "[GIT] cloning repo..."
  rm -rf "$INSTALL_DIR" 2>/dev/null || true
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --depth=1 "$REPO" "$INSTALL_DIR"
fi

# ── download binary + rulesets ────────────────────────────
echo "[DOWNLOAD] 下载二进制和规则文件..."
bash "$INSTALL_DIR/mimo443/download.sh" --force

# ── install ───────────────────────────────────────────────
echo "[INSTALL] starting..."
MIMO_UUID="$MIMO_UUID" MIMO_PASS="$MIMO_PASS" bash "$INSTALL_DIR/mimo443/start.sh" install

# ── enable tproxy ─────────────────────────────────────────
echo "[TPROXY] 启用透明代理..."
systemctl enable --now mimo-tproxy.service 2>/dev/null || true

echo ""
echo "============================================"
echo "  mimo 安装完成!"
echo "  console: http://$(curl -s --max-time 2 ifconfig.me 2>/dev/null || echo 'VPS_IP'):2000"
echo "  user: admin12  pass: ${MIMO_PASS}"
echo "  manage: bash $INSTALL_DIR/mimo443/start.sh"
echo "============================================"
