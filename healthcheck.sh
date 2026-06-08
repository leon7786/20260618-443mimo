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
