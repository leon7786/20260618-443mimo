#!/usr/bin/env bash
# 下载 mimo 二进制和规则文件
# 用法: bash download.sh [--force]
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
FORCE="${1:-}"
RELEASE_BASE="https://github.com/leon7786/20260618-443mimo/releases/latest/download"

# 规则文件 CDN
RULES=(
  "cn_domain.mrs|https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@meta/geo/geosite/cn.mrs"
  "cn_ip.mrs|https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@meta/geo/geoip/cn.mrs"
  "private.mrs|https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@meta/geo/geosite/private.mrs"
)

select_binary_name() {
  case "$(uname -m)" in
    x86_64|amd64) echo "mimo-linux-amd64" ;;
    *)            echo "mimo-linux-arm64-a53" ;;
  esac
}

download_binary() {
  local bin_name; bin_name="$(select_binary_name)"
  local bin_path="${APP_DIR}/${bin_name}"

  if [ -f "$bin_path" ] && [ "$FORCE" != "--force" ]; then
    echo "[BIN] ${bin_name} 已存在 (跳过, 用 --force 强制更新)"
    return
  fi

  echo "[BIN] 下载 ${bin_name} ..."
  mkdir -p "${APP_DIR}"
  curl -fSL --progress-bar -o "${bin_path}" "${RELEASE_BASE}/${bin_name}"
  chmod +x "${bin_path}"
  echo "[BIN] OK: ${bin_path} ($(du -h "$bin_path" | cut -f1))"
}

download_rulesets() {
  mkdir -p "${APP_DIR}/ruleset"
  for entry in "${RULES[@]}"; do
    local name="${entry%%|*}"
    local url="${entry##*|}"
    local path="${APP_DIR}/ruleset/${name}"
    if [ -f "$path" ] && [ "$FORCE" != "--force" ]; then
      echo "[RULE] ${name} 已存在 (跳过)"
      continue
    fi
    echo "[RULE] 下载 ${name} ..."
    curl -fSL --progress-bar -o "${path}" "${url}"
    echo "[RULE] OK: ${name} ($(du -h "$path" | cut -f1))"
  done
}

download_binary
download_rulesets
echo "[DONE] 下载完成"
