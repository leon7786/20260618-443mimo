#!/usr/bin/env bash
# mimo 一键安装 — VPS 透明代理部署
# 用法: bash <(curl -fsSL https://raw.githubusercontent.com/leon7786/20260618-443mimo/master/install.sh)
set -euo pipefail

REPO="https://github.com/leon7786/20260618-443mimo.git"
TMPDIR="$(mktemp -d -t mimo-install.XXXXXX)"
INSTALL_DIR="/root/projects/20260515-mimo443"

cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

[ "$(id -u)" -ne 0 ] && { echo "[ERROR] 需要 root 权限: sudo bash install.sh" >&2; exit 1; }

# ── dependencies ──────────────────────────────────────────
if ! command -v git >/dev/null 2>&1; then
  echo "[DEPS] 安装 git..."
  apt-get update -qq 2>/dev/null && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git 2>/dev/null || \
  yum install -y -q git 2>/dev/null || \
  { echo "[ERROR] git 安装失败，请手动安装"; exit 1; }
fi

# ── clone ──────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "[GIT] 已有仓库，更新..."
  git -C "$INSTALL_DIR" pull --ff-only origin master 2>/dev/null || true
else
  echo "[GIT] 克隆仓库..."
  rm -rf "$INSTALL_DIR" 2>/dev/null || true
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --depth=1 "$REPO" "$INSTALL_DIR"
fi

# ── install ────────────────────────────────────────────────
echo "[INSTALL] 开始安装..."
bash "$INSTALL_DIR/mimo443/start.sh" install

echo ""
echo "============================================"
echo "  一键安装完成。"
echo "  控制台: http://$(curl -s --max-time 2 ifconfig.me 2>/dev/null || echo '服务器IP'):2000"
echo "  账号: admin12  密码: Dd--2131801"
echo "  管理: bash $INSTALL_DIR/mimo443/start.sh"
echo "============================================"
