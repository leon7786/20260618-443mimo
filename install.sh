#!/usr/bin/env bash
# mimo 一键安装 — VPS 代理部署
# 用法: bash <(curl -fsSL https://raw.githubusercontent.com/leon7786/20260618-443mimo/master/install.sh)
#   或: MIMO_UUID=xxx MIMO_PASS=yyy bash install.sh   (非交互)
set -euo pipefail

REPO="https://github.com/leon7786/20260618-443mimo.git"
TMPDIR="$(mktemp -d -t mimo-install.XXXXXX)"
INSTALL_DIR="/root/projects/20260515-mimo443"

cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

[ "$(id -u)" -ne 0 ] && { echo "[ERROR] need root: sudo bash install.sh" >&2; exit 1; }

# ── interactive prompts ──────────────────────────────────
if [ -z "${MIMO_UUID:-}" ]; then
  echo ""
  echo "========================================"
  echo "  mimo 安装向导"
  echo "========================================"
  read -r -p "  控制台登录密码 : " MIMO_PASS
  read -r -p "  UUID (节点默认密码) : " MIMO_UUID
  echo ""
fi

MIMO_PASS="${MIMO_PASS:-admin12}"
MIMO_UUID="${MIMO_UUID:-$(cat /proc/sys/kernel/random/uuid 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())')}"

echo "[INFO] user: admin12  pass: ${MIMO_PASS}  uuid: ${MIMO_UUID}"
export MIMO_PASS MIMO_UUID

# ── dependencies ──────────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
  echo "[DEPS] installing git..."
  apt-get update -qq 2>/dev/null && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git 2>/dev/null || \
  yum install -y -q git 2>/dev/null || \
  { echo "[ERROR] git install failed"; exit 1; }
fi

# ── clone ──────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "[GIT] pulling updates..."
  git -C "$INSTALL_DIR" pull --ff-only origin master 2>/dev/null || true
else
  echo "[GIT] cloning repo..."
  rm -rf "$INSTALL_DIR" 2>/dev/null || true
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --depth=1 "$REPO" "$INSTALL_DIR"
fi

# ── install ────────────────────────────────────────────────
echo "[INSTALL] starting..."
MIMO_UUID="$MIMO_UUID" MIMO_PASS="$MIMO_PASS" bash "$INSTALL_DIR/mimo443/start.sh" install

echo ""
echo "============================================"
echo "  mimo installed."
echo "  console: http://$(curl -s --max-time 2 ifconfig.me 2>/dev/null || echo 'VPS_IP'):2000"
echo "  user: admin12  pass: ${MIMO_PASS}"
echo "  manage: bash $INSTALL_DIR/mimo443/start.sh"
echo "============================================"
