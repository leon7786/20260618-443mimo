#!/usr/bin/env python3
import base64
import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse

import yaml

APP_DIR = Path(os.environ.get("APP_DIR") or Path(__file__).resolve().parent.parent)
CONFIG_PATH = APP_DIR / "config.yaml"
CERTS_DIR = APP_DIR / "certs"
CONSOLE_DIR = APP_DIR / "console"
AUTH_PATH = CONSOLE_DIR / "console-auth.yaml"
STATE_PATH = CONSOLE_DIR / "state.yaml"
INIT_MARKER_PATH = CONSOLE_DIR / ".initialized"
HOST = os.environ.get("CONSOLE_HOST", "0.0.0.0")
PORT = int(os.environ.get("CONSOLE_PORT", "2000"))
MIMO_SERVICE_NAME = os.environ.get("MIMO_SERVICE_NAME", "mimo.service")
MIMO_BINARY = Path(os.environ.get("MIMO_BINARY", str(APP_DIR / "mimo-linux-amd64")))
CERT_PATH = "./certs/server.crt"
KEY_PATH = "./certs/server.key"
HYSTERIA2_OBFS_PASSWORD = "OWQwMjliNDEwYjA2OWQwMw=="
MIHOMO_CONTROLLER = "127.0.0.1:19093"
LOCK = threading.Lock()
IP_CACHE = {"ip": "", "updated_at": 0.0, "refreshing": False, "error": ""}
IP_CACHE_LOCK = threading.Lock()

HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>mimo 控制台</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop stop-color='%2360a5fa'/%3E%3Cstop offset='1' stop-color='%231d4ed8'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='64' height='64' rx='14' fill='%23dbeafe'/%3E%3Cpath d='M15 25 20 10l10 8h4l10-8 5 15c4 5 5 13 2 20-4 9-13 13-19 13S17 54 13 45c-3-7-2-15 2-20Z' fill='url(%23g)'/%3E%3Ccircle cx='24' cy='34' r='4' fill='white'/%3E%3Ccircle cx='40' cy='34' r='4' fill='white'/%3E%3Ccircle cx='25' cy='35' r='2' fill='%230f172a'/%3E%3Ccircle cx='39' cy='35' r='2' fill='%230f172a'/%3E%3Cpath d='M29 42h6l-3 4Z' fill='%23bfdbfe'/%3E%3Cpath d='M23 49c5 3 13 3 18 0' stroke='white' stroke-width='3' stroke-linecap='round' fill='none'/%3E%3C/svg%3E">
  <style>
    :root {
      color-scheme: light;
      --bg:#d9e4ef; --bg-soft:#eef4fa; --panel:#f8fbfe; --card:#ffffff;
      --text:#1f3349; --muted:#5f7489; --line:#b8c8d8; --line-strong:#8fa6ba;
      --accent:#2b78b8; --accent-soft:#e4f0fb; --accent-strong:#155d92;
      --purple:#476f96; --purple-soft:#e7eff7; --warning:#b36b00; --warning-soft:#fff3d6;
      --bad:#b72a2a; --bad-soft:#f8dfdf; --ok:#23845f; --ok-soft:#ddf2e9;
      --shadow:0 10px 24px rgba(35, 59, 83, .16); --shadow-soft:0 3px 12px rgba(35, 59, 83, .12);
    }
    * { box-sizing: border-box; }
    body {
      margin:0; min-height:100vh; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        linear-gradient(180deg, rgba(255,255,255,.38), rgba(255,255,255,0) 130px),
        repeating-linear-gradient(0deg, rgba(255,255,255,.24) 0, rgba(255,255,255,.24) 1px, transparent 1px, transparent 32px),
        linear-gradient(180deg, var(--bg-soft), var(--bg));
      color:var(--text);
    }
    header {
      width:min(1880px, calc(100% - 28px)); margin:12px auto 0; padding:12px 16px;
      border:1px solid #87a5bf; border-radius:10px; display:flex; justify-content:space-between; gap:12px; align-items:center; flex-wrap:nowrap;
      background:linear-gradient(180deg, #3f83bd, #23669c); color:#fff; box-shadow:var(--shadow); overflow-x:auto;
    }
    .header-main { display:flex; align-items:center; gap:10px; min-width:max-content; }
    .header-title-row { display:flex; align-items:center; gap:10px; flex-wrap:nowrap; }
    .header-subtitle { display:flex; align-items:center; gap:7px; flex-wrap:nowrap; }
    .header-chip { display:inline-flex; align-items:center; padding:4px 8px; border:1px solid rgba(255,255,255,.28); border-radius:999px; background:rgba(255,255,255,.14); color:#f3f9ff; font-size:12px; font-weight:750; box-shadow:inset 0 1px 0 rgba(255,255,255,.14); }
    .header-actions { display:flex; align-items:center; gap:8px; padding:6px 8px; border:1px solid rgba(255,255,255,.28); border-radius:8px; background:rgba(9,46,78,.22); box-shadow:inset 0 1px 0 rgba(255,255,255,.12); min-width:max-content; }
    .header-status { display:flex; align-items:center; gap:7px; min-width:max-content; }
    .header-status-label { font-size:11px; color:#d9efff; font-weight:800; letter-spacing:.02em; white-space:nowrap; }
    header .pill { background:#f8fbff; color:#155d92; border-color:rgba(255,255,255,.65); justify-content:center; }
    header button.secondary { background:linear-gradient(180deg, #ffffff, #dcecf8); color:#155d92; border-color:rgba(255,255,255,.75); }
    h1 { margin:0; font-size:24px; letter-spacing:-.03em; }
    h2 { margin:0 0 8px; font-size:18px; letter-spacing:-.02em; }
    h3 { margin:0 0 6px; font-size:15px; letter-spacing:-.01em; }
    main { width:min(1880px, calc(100% - 28px)); margin:0 auto; padding:12px 0 18px; display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1fr); grid-template-areas:"local chain" "log log"; gap:12px; align-items:start; }
    section, .card { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:12px; box-shadow:var(--shadow-soft); }
    section.local-block { grid-area:local; border-color:#94adbf; background:linear-gradient(180deg, #f9fcff, #edf4fa); }
    section.chain-block { grid-area:chain; border-color:#94adbf; background:linear-gradient(180deg, #f9fcff, #edf4fa); }
    section.log-block { grid-area:log; border-color:#b7aa87; background:linear-gradient(180deg, #fff9e8, #fff3cf); }
    section > .row:first-child { padding-bottom:8px; border-bottom:1px solid rgba(217,226,242,.72); }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap:12px; }
    label { display:block; font-size:12px; color:var(--muted); margin:6px 0 3px; }
    input:not([type="radio"]):not([type="checkbox"]), textarea {
      width:100%; border:1px solid #aabccd; background:#fbfdff; color:var(--text); border-radius:5px; padding:8px 10px;
      font:12.5px ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; outline:none; transition:border-color .16s, box-shadow .16s, background .16s;
    }
    input[type="radio"] { width:auto; accent-color:var(--accent); margin-right:5px; }
    textarea { min-height:96px; resize:vertical; line-height:1.38; }
    input:not([type="radio"]):not([type="checkbox"]):focus, textarea:focus { border-color:rgba(37,99,235,.68); box-shadow:0 0 0 4px rgba(37,99,235,.11); background:#fff; }
    button {
      border:1px solid #0f5687; border-radius:5px; padding:8px 12px; background:linear-gradient(180deg, #3d91ce, #1f6fa8); color:white;
      font-size:13px; font-weight:750; cursor:pointer; box-shadow:0 8px 18px rgba(37,99,235,.22); transition:transform .14s, box-shadow .14s, opacity .14s, background .14s;
    }
    button:hover:not(:disabled) { transform:translateY(-1px); box-shadow:0 12px 24px rgba(37,99,235,.26); }
    button.secondary { background:linear-gradient(180deg, #ffffff, #e6eef6); color:#244760; border:1px solid #9cb2c5; box-shadow:0 2px 5px rgba(35,59,83,.12); }
    button.secondary:hover:not(:disabled) { border-color:var(--line-strong); box-shadow:0 10px 22px rgba(31,41,55,.10); }
    button.action-add { background:linear-gradient(180deg, #3d91ce, #1f6fa8); border-color:#0f5687; color:white; }
    button.action-test { background:linear-gradient(180deg, #3d91ce, #1f6fa8); border-color:#0f5687; color:white; }
    button.action-copy { background:linear-gradient(180deg, #ffffff, #dfeaf3); color:#244760; border:1px solid #9cb2c5; box-shadow:0 2px 5px rgba(35,59,83,.12); }
    button.action-clear { background:linear-gradient(180deg, #fff8e5, #ead394); color:#6f4b00; border:1px solid #b7aa87; box-shadow:none; padding:5px 9px; font-size:12px; }
    button.danger, button.action-danger { background:linear-gradient(135deg, #ef4444, var(--bad)); color:white; box-shadow:0 8px 18px rgba(220,38,38,.20); }
    button.success { background:linear-gradient(180deg, #35a878, #23845f); border-color:#1c6b4d; color:white; }
    button.failed { background:linear-gradient(180deg, #d64b4b, #a92a2a); border-color:#842020; color:white; }
    button:disabled { opacity:.55; cursor:not-allowed; transform:none; }
    .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
    .muted { color:var(--muted); font-size:12px; }
    header .muted { color:#eaf6ff; text-shadow:0 1px 2px rgba(0,0,0,.28); font-weight:650; }
    .status { white-space:pre-wrap; background:#102b43; border:1px solid #0a2033; border-radius:5px; padding:10px 12px; max-height:180px; overflow:auto; color:#dcecf8; box-shadow: inset 0 1px 2px rgba(0,0,0,.24); }
    .log-block { display:block; padding:8px 10px; }
    .log-head { display:flex; align-items:center; justify-content:space-between; gap:10px; margin:0 0 5px; }
    .log-block h2 { margin:0; font-size:13px; white-space:nowrap; color:#6f4b00; }
    .log-output { height:520px; max-height:520px; overflow:auto; font-size:10.5px; line-height:1.35; white-space:pre-wrap; }
    .log-output.expanded { height:calc(60 * 1.35em + 18px); max-height:calc(60 * 1.35em + 18px); }
    .cards { display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:10px; margin-top:10px; }
    .card { background:var(--card); border-color:#b6c7d6; transition:box-shadow .16s, border-color .16s; }
    .card:hover { border-color:#7f9bb3; box-shadow:0 4px 14px rgba(35,59,83,.16); }
    .card-head { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; margin-bottom:6px; }
    .card-title { display:flex; align-items:center; gap:8px; flex-wrap:wrap; min-width:0; }
    .card-actions { display:flex; gap:7px; align-items:center; flex-wrap:wrap; margin-top:8px; }
    .service-summary { margin-top:3px; color:#5f7489; font-size:12px; font-weight:700; }
    .summary-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:8px; margin:10px 0; }
    .chain-tools { display:flex; justify-content:space-between; align-items:center; gap:18px; margin:12px 0; padding:8px 10px; border:1px solid #c3d2df; border-radius:6px; background:linear-gradient(180deg, #ffffff, #edf4fa); }
    .chain-tools .tool-left, .chain-tools .tool-right { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .preview-actions { display:flex; justify-content:flex-end; margin-top:8px; }
    .chain-preview.collapsed { display:none; }
    .summary-card { border:1px solid #b6c7d6; border-radius:6px; background:#fff; padding:8px 10px; min-width:0; }
    .summary-title { font-size:11px; color:var(--muted); font-weight:800; margin-bottom:4px; }
    .summary-value { font-size:13px; color:var(--text); font-weight:850; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .summary-sub { margin-top:3px; font-size:11px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .switch { position:relative; display:inline-block; width:50px; height:28px; flex:0 0 auto; }
    .switch input { display:none; }
    .slider { position:absolute; cursor:pointer; inset:0; background:#cbd5e1; transition:.2s; border-radius:999px; box-shadow:inset 0 1px 3px rgba(15,23,42,.18); }
    .slider:before { position:absolute; content:""; height:22px; width:22px; left:3px; top:3px; background:white; transition:.2s; border-radius:50%; box-shadow:0 3px 8px rgba(15,23,42,.22); }
    .switch input:checked + .slider { background:#cbd5e1; }
    .switch input:checked + .slider:before { transform:translateX(22px); }
    .switch.on input:checked + .slider { background:linear-gradient(135deg, #10b981, var(--ok)); }
    .switch.starting .slider { background:linear-gradient(135deg, #93c5fd, var(--accent)); }
    .switch.starting .slider:before { box-shadow:0 0 0 5px rgba(37,99,235,.16), 0 3px 8px rgba(15,23,42,.22); }
    .pill { display:inline-flex; align-items:center; gap:6px; padding:4px 9px; border-radius:4px; background:#dcebf7; color:#1f5d8c; border:1px solid #9fb9ce; font-size:12px; font-weight:700; }
    .connection { display:inline-flex; align-items:center; gap:8px; padding:6px 10px; border-radius:4px; border:1px solid #a9bdce; background:#fff; color:var(--muted); font-size:13px; font-weight:700; }
    .connection .dot { width:10px; height:10px; border-radius:50%; background:#94a3b8; box-shadow:0 0 0 4px rgba(148,163,184,.16); }
    .connection.connected { color:var(--ok); border-color:rgba(5,150,105,.25); background:var(--ok-soft); }
    .connection.connected .dot { background:#22c55e; box-shadow:0 0 0 4px rgba(34,197,94,.18), 0 0 10px #22c55e, 0 0 22px #16a34a, 0 0 36px rgba(132,255,173,.95); animation:greenSpark 1.05s infinite alternate; }
    @keyframes greenSpark { 0% { transform:scale(.9); filter:brightness(1); box-shadow:0 0 0 3px rgba(34,197,94,.14), 0 0 8px #22c55e, 0 0 16px rgba(34,197,94,.65); } 45% { transform:scale(1.15); filter:brightness(1.55); box-shadow:0 0 0 6px rgba(34,197,94,.22), 0 0 14px #86efac, 0 0 28px #22c55e, 0 0 46px rgba(132,255,173,.9); } 100% { transform:scale(1); filter:brightness(1.2); box-shadow:0 0 0 4px rgba(34,197,94,.18), 0 0 12px #4ade80, 0 0 24px #16a34a; } }
    .connection.failed { color:var(--bad); border-color:rgba(220,38,38,.25); background:var(--bad-soft); }
    .connection.failed .dot { background:var(--bad); box-shadow:0 0 0 4px rgba(220,38,38,.16); }
    .connection.unknown { color:var(--muted); border-color:rgba(148,163,184,.32); }
    .connection.testing { color:var(--accent); border-color:rgba(37,99,235,.25); background:var(--accent-soft); }
    .connection.testing .dot { background:var(--accent); box-shadow:0 0 0 4px rgba(37,99,235,.16), 0 0 14px rgba(37,99,235,.42); }
    .connection-detail { color:var(--muted); font-size:12px; margin-left:8px; }
    .protocol-group { display:inline-flex; align-items:center; gap:6px; border:1px solid #b8c8d8; border-radius:6px; padding:4px; background:rgba(255,255,255,.72); flex-wrap:wrap; }
    .protocol-group button.action-add { padding:6px 10px; border-radius:4px; box-shadow:0 1px 3px rgba(35,59,83,.10); }
    .perf-panel { margin:10px 0; padding:8px 10px; border:1px solid #c3d2df; border-radius:6px; background:linear-gradient(180deg, #ffffff, #edf4fa); }
    .perf-head { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:8px; }
    .perf-title { font-size:13px; font-weight:850; color:#244760; }
    .perf-grid { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .perf-check { display:inline-flex; align-items:center; gap:6px; margin:0; padding:6px 9px; border:1px solid #9cb2c5; border-radius:4px; background:#fff; color:#244760; font-size:12px; font-weight:750; cursor:pointer; box-shadow:0 1px 3px rgba(35,59,83,.10); }
    .perf-check input { accent-color:var(--accent); }
    .perf-field { display:inline-flex; align-items:center; gap:6px; margin:0; padding:5px 8px; border:1px solid #9cb2c5; border-radius:4px; background:#fff; color:#244760; font-size:12px; font-weight:750; }
    .perf-field select { border:1px solid #b8c8d8; border-radius:4px; background:#f8fbfe; color:#244760; padding:4px 6px; font-size:12px; outline:none; }
    .service-state { font-size:12px; color:var(--muted); font-weight:700; }
    .service-state.on { color:var(--ok); }
    .service-state.failed { color:var(--bad); }
    @media (min-width: 1500px) { .local-block .cards { grid-template-columns: repeat(2, minmax(0, 1fr)); } #chainNodes { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:10px; } }
    @media (max-width: 1180px) { main { grid-template-columns:1fr; grid-template-areas:"local" "chain" "log"; } }
    @media (max-width: 760px) { header, main { width:min(100% - 20px, 1440px); } header { padding:14px; border-radius:8px; } section, .card { padding:12px; border-radius:8px; } .cards, #chainNodes { grid-template-columns:1fr; } .log-output { height:400px; max-height:400px; } }
  </style>
</head>
<body>
<header>
  <div class="header-main">
    <div class="header-title-row"><h1>mimo 控制台</h1><span class="header-chip">Mimo Binary</span></div>
    <div class="header-subtitle"><span class="header-chip">一键搭建高性能本地服务端</span><span class="header-chip">链式代理</span></div>
  </div>
  <div class="header-actions">
    <div class="header-status"><span class="header-status-label">容器状态</span><span id="statusPill" class="pill">加载中</span></div>
    <button class="secondary" onclick="loadState()">刷新状态</button>
  </div>
</header>
<main>
  <section class="log-block">
    <div class="log-head" style="justify-content:flex-start"><h2>日志</h2><div class="row"><button class="action-clear" onclick="toggleLogExpand(this)">展开</button><button class="action-clear" onclick="copyLog(this)">复制</button><button class="action-clear" onclick="clearLog()">清空</button></div></div>
    <div id="output" class="status log-output">等待操作。</div>
  </section>

  <section class="local-block">
    <div class="row" style="justify-content:space-between; margin-bottom:12px"><h2 style="margin:0">搭建本地服务端</h2><div class="row"><div class="protocol-group"><button class="action-add" onclick="addLocalService('tuic')">TUIC</button><button class="action-add" onclick="addLocalService('hysteria2')">Hysteria2</button><button class="action-add" onclick="addLocalService('anytls')">AnyTLS</button><button class="action-add" onclick="addLocalService('ss')">SS</button><button class="action-add" onclick="addLocalService('http')">HTTP</button><button class="action-add" onclick="addLocalService('socks')">SOCKS5</button></div></div></div>
    <textarea id="localPaste" placeholder="也可以手动粘贴单个服务端 YAML，再点手动增加"></textarea>
    <div class="row" style="margin-top:10px"><button class="action-add" onclick="parseLocal()">手动增加服务端</button><span class="muted">点击标题右侧协议按钮会直接新增一个默认关闭的服务端卡片。</span></div>
    <div id="localCards" class="cards"></div>
  </section>

  <section class="chain-block">
    <div class="row" style="justify-content:space-between; margin-bottom:12px"><div class="row"><h2 style="margin:0">搭建链式代理</h2><label class="switch"><input id="applySwitch" type="checkbox" onchange="applyConfig(this)"><span class="slider"></span></label><span id="applySwitchText" style="display:none"></span><span id="connectionStatus" class="connection unknown" title="尚未测试"><span class="dot"></span><span id="connectionText">未测试</span></span><span id="connectionDetail" class="connection-detail"></span></div><div class="row"><button id="connectivityBtn" class="action-test" onclick="testConnectivityOnly(this)">连通性测试</button><button class="secondary" onclick="fillEntryExample('ss')">SS入口</button><button class="secondary" onclick="fillEntryExample('http')">HTTP入口</button><button class="secondary" onclick="fillEntryExample('socks')">SOCKS5入口</button><button id="validateBtn" class="action-test" onclick="validateOnly()">只校验</button></div></div>
    <div id="chainSummary" class="summary-grid"></div>
    <div class="perf-panel">
      <div class="perf-head"><span class="perf-title">性能优化</span><span class="muted">切换后会保存 config.yaml 并重启 Mihomo</span></div>
      <div class="perf-grid">
        <label class="perf-check" title="通过 iptables REDIRECT 劫持本机所有 TCP+DNS 流量进 mimo，实现整机透明代理。开启后无需设置 http_proxy 环境变量。"><input id="perfTproxy" type="checkbox" onchange="applyPerformanceSettings()">VPS透明代理</label>
        <label class="perf-check" title="保持空闲连接更久，减少频繁重新建连；建议开启。"><input id="perfKeepAlive" type="checkbox" onchange="applyPerformanceSettings()">长连接</label>
        <label class="perf-check" title="同一目标有多个 IP 时并发尝试连接，优先使用最快可达线路；建议开启。"><input id="perfTcpConcurrent" type="checkbox" onchange="applyPerformanceSettings()">TCP并发</label>
        <label class="perf-check" title="统一延迟计算方式，让测速和状态显示更稳定；建议开启。" style="display:none"><input id="perfUnifiedDelay" type="checkbox" onchange="applyPerformanceSettings()">统一延迟</label>
<!-- Fake-IP removed: always redir-host -->
        <label class="perf-check" title="开：大陆白名单分流（国内直连，其余走代理出口，3 个规则文件）。关：全局代理（除内网外全部走代理出口）。"><input id="perfSplitRoute" type="checkbox" onchange="applyPerformanceSettings()">国内外分流</label>
        <label class="perf-check" title="允许 IPv6 解析和连接；纯 IPv4 服务器建议关闭，避免 AAAA 连接失败。"><input id="perfIpv6" type="checkbox" onchange="applyPerformanceSettings()">IPv6</label>
        <label class="perf-field" title="连接失败等待时间。3秒更快失败，5秒较均衡，10秒适合慢线路。">超时<select id="perfTimeout" onchange="applyPerformanceSettings()"><option value="3">3秒</option><option value="5">5秒</option><option value="10">10秒</option></select></label>
        <label class="perf-field" title="日志详细程度。error 最安静，warning 推荐日常使用，debug 只建议排查问题时开启。">日志<select id="perfLogLevel" onchange="applyPerformanceSettings()"><option value="error">error</option><option value="warning">warning</option><option value="info">info</option><option value="debug">debug</option></select></label>
      </div>
    </div>
    <label>第1级入口节点</label>
    <textarea id="entryText" placeholder="选择 SS / HTTP / SOCKS5 自动填入入口节点，也可以手动粘贴"></textarea>
    <div class="chain-tools"><div class="tool-left"><span class="muted">快速生成下级节点</span><button class="action-copy" onclick="fillAnyTlsChainExample()">填入第2级 AnyTLS 范例</button></div><div class="tool-right"><button class="action-add" onclick="addChainNode()">+ 增加下一级</button></div></div>
    <div id="chainNodes"></div>
    <div class="preview-actions"><button id="chainPreviewBtn" class="action-copy" onclick="toggleChainPreview()">链路预览</button></div>
    <div id="chainPreview" class="status muted chain-preview collapsed">尚未生成链路预览。</div>
  </section>

</main>
<script>
let state = {version:1, local_services:[], chain:{enabled:true, entry_text:'', node_texts:[['']], entry:null, nodes:[]}, managed:{listener_names:[], proxy_names:[], proxy_group_names:[]}};
let publicIp = '';

const LOCAL_EXAMPLES = {
  tuic: `- type: tuic
  server: 0.0.0.0
  port: 2087
  uuid: 667547af-159f-4059-9443-ed4eb326a438
  password: ZOwpXCwS7v5_0aJqn3XP9EKi
  sni: www.sciencedirect.com
  alpn:
    - h3
  skip-cert-verify: true
  disable-sni: false
  congestion-controller: bbr
  udp: true`,
  hysteria2: `- type: hysteria2
  server: 0.0.0.0
  port: 2055
  password: 667547af-159f-4059-9443-ed4eb326a438
  up: "200 Mbps"
  down: "200 Mbps"
  obfs: salamander
  obfs-password: OWQwMjliNDEwYjA2OWQwMw==
  alpn:
    - h3
  skip-cert-verify: true
  udp: true`,
  anytls: `- type: anytls
  server: 0.0.0.0
  port: 2096
  password: 667547af-159f-4059-9443-ed4eb326a438
  sni: ''
  alpn:
    - h2
    - http/1.1
  skip-cert-verify: true
  client-fingerprint: chrome
  udp: true`,
  ss: `- type: ss
  server: 0.0.0.0
  port: 2093
  cipher: 2022-blake3-aes-128-gcm
  password: ZnVHrxWfQFmUQ+1OsyakOA==
  udp: true`,
  http: `- type: http
  server: 0.0.0.0
  port: 18080
  username: your_username
  password: your_password`,
  socks: `- type: socks
  server: 0.0.0.0
  port: 11080
  username: your_username
  password: your_password
  udp: true`
};

const ENTRY_EXAMPLES = {
  ss: `- name: chain-entry-ss-14001
  type: ss
  server: 0.0.0.0
  port: 14001
  cipher: 2022-blake3-aes-128-gcm
  password: ZnVHrxWfQFmUQ+1OsyakOA==
  udp: true`,
  http: `- name: chain-entry-http-2001
  type: http
  server: 0.0.0.0
  port: 2001
  username: admin123
  password: admin1234`,
  socks: `- name: chain-entry-socks5-11081
  type: socks
  server: 0.0.0.0
  port: 11081
  username: your_username
  password: your_password
  udp: true`
};

const ANYTLS_CHAIN_EXAMPLE = `- name: chain-anytls-2096
  type: anytls
  server: 132.226.23.12
  port: 2096
  password: 667547af-159f-4059-9443-ed4eb326a438
  sni: ''
  alpn:
    - h2
    - http/1.1
  skip-cert-verify: true
  client-fingerprint: chrome
  udp: true`;

function writeLog(text, append=false){
  const el = document.getElementById('output');
  if(append && el.textContent && el.textContent !== '等待操作。') el.textContent += '\n' + text;
  else el.textContent = text;
  requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
}
function out(msg){ writeLog(typeof msg === 'string' ? msg : JSON.stringify(msg,null,2)); }
function appendLog(msg){ writeLog(typeof msg === 'string' ? msg : JSON.stringify(msg,null,2), true); }
function clearLog(){ writeLog('等待操作。'); }
function toggleLogExpand(btn){
  const el = document.getElementById('output');
  if(!el) return;
  const expanded = el.classList.toggle('expanded');
  if(btn) btn.textContent = expanded ? '收起' : '展开';
}
async function copyLog(btn){
  const el = document.getElementById('output');
  const old = btn ? btn.textContent : '复制';
  try{
    await copyText(el ? el.textContent : '');
    if(btn) btn.textContent = '已复制';
  } catch(e){
    if(btn) btn.textContent = '复制失败';
    out(e);
  } finally {
    if(btn) setTimeout(() => { btn.textContent = old; }, 1500);
  }
}
async function api(path, data){
  const res = await fetch(path, {method:data===undefined?'GET':'POST', cache:'no-store', headers:{'Content-Type':'application/json','Cache-Control':'no-cache'}, body:data===undefined?undefined:JSON.stringify(data)});
  const txt = await res.text();
  let body; try { body = txt ? JSON.parse(txt) : {}; } catch(e) { body = {ok:false, error:txt}; }
  if(!res.ok) throw body;
  return body;
}
const undoStates = new WeakMap();
function textControlSelector(){ return 'textarea, input[type="text"], input[type="password"], input[type="number"], input[type="search"], input[type="url"], input[type="email"], input:not([type])'; }
function getUndoState(el){
  let s = undoStates.get(el);
  if(!s){ s = {undo:[el.value || ''], redo:[], last:el.value || ''}; undoStates.set(el, s); }
  return s;
}
function recordUndoValue(el){
  const s = getUndoState(el);
  const value = el.value || '';
  if(value === s.last) return;
  s.undo.push(value);
  if(s.undo.length > 120) s.undo.shift();
  s.redo = [];
  s.last = value;
}
function setTextControlValue(el, value){
  el.value = value;
  el.dispatchEvent(new Event('input', {bubbles:true}));
  el.dispatchEvent(new Event('change', {bubbles:true}));
}
function undoTextControl(el){
  const s = getUndoState(el);
  if(s.undo.length <= 1) return;
  const current = s.undo.pop();
  s.redo.push(current);
  const value = s.undo[s.undo.length - 1];
  s.last = value;
  setTextControlValue(el, value);
}
function redoTextControl(el){
  const s = getUndoState(el);
  if(!s.redo.length) return;
  const value = s.redo.pop();
  s.undo.push(value);
  s.last = value;
  setTextControlValue(el, value);
}
function initUndoForTextControls(root=document){
  root.querySelectorAll(textControlSelector()).forEach(el => getUndoState(el));
}
document.addEventListener('focusin', e => { if(e.target.matches && e.target.matches(textControlSelector())) getUndoState(e.target); });
document.addEventListener('input', e => { if(e.target.matches && e.target.matches(textControlSelector())) recordUndoValue(e.target); });
document.addEventListener('keydown', e => {
  const el = e.target;
  if(!el || !el.matches || !el.matches(textControlSelector()) || !(e.ctrlKey || e.metaKey)) return;
  const key = e.key.toLowerCase();
  if(key === 'z'){
    e.preventDefault();
    if(e.shiftKey) redoTextControl(el); else undoTextControl(el);
  } else if(key === 'y'){
    e.preventDefault();
    redoTextControl(el);
  }
});
function yamlText(obj){ return obj.yaml || ''; }
function escapeHtml(s){ return String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function setConnectionStatus(status, text, detail=''){
  const el = document.getElementById('connectionStatus');
  const label = document.getElementById('connectionText');
  const detailEl = document.getElementById('connectionDetail');
  el.className = 'connection ' + (status || 'unknown');
  label.textContent = text;
  el.title = detail || text;
  if(detailEl) detailEl.textContent = '';
  renderChainSummary();
}
function connectivityDetail(conn){
  if(!conn) return '';
  const parts = [];
  if(conn.mode) parts.push(conn.mode);
  if(conn.checked_at) parts.push(conn.checked_at);
  if(conn.returncode !== undefined) parts.push('code ' + conn.returncode);
  if(conn.elapsed_ms !== undefined) parts.push(conn.elapsed_ms + 'ms');
  if(conn.output && !conn.ok) parts.push(String(conn.output).split('\n').filter(Boolean).slice(-1)[0]);
  return parts.join(' · ');
}
function connectivityLogLine(conn){
  if(!conn) return '连通性测试无结果';
  const status = conn.ok ? '成功' : '失败';
  return `连通性测试${status}：${connectivityDetail(conn)}`;
}
function toggleChainPreview(){
  const preview = document.getElementById('chainPreview');
  const btn = document.getElementById('chainPreviewBtn');
  if(!preview) return;
  const collapsed = preview.classList.toggle('collapsed');
  if(btn) btn.textContent = collapsed ? '链路预览' : '收起预览';
}
function connectivityBadgeText(conn){
  if(conn && conn.ok) return conn.elapsed_ms !== undefined ? `Google连接成功! ${conn.elapsed_ms}ms` : 'Google连接成功!';
  if(conn && conn.checked_at) return conn.elapsed_ms !== undefined ? `Google FAIL · ${conn.elapsed_ms}ms` : 'Google FAIL';
  return '未测试';
}
function nodeSummary(node, fallback){
  node = node || {};
  const type = node.type || fallback || '未配置';
  const port = node.port !== undefined && node.port !== null ? node.port : '-';
  const name = node.name || node.server || '等待配置';
  return {type, port, name};
}
function chainProxyUrl(){
  const entry = state.chain && state.chain.entry;
  if(!entry || !entry.type || !entry.port || !publicIp) return '';
  const type = String(entry.type).toLowerCase();
  if(type !== 'http' && type !== 'socks') return '';
  let auth = '';
  const users = entry.users || [];
  if(Array.isArray(users) && users.length){
    const u = encodeURIComponent(users[0].username || '');
    const p = encodeURIComponent(users[0].password || '');
    if(u || p) auth = `${u}:${p}@`;
  }
  const scheme = type === 'socks' ? 'socks5' : 'http';
  return `${scheme}://${auth}${publicIp}:${entry.port}`;
}
function proxySetupGuide(url){
  return `临时生效：当前 SSH 窗口\n\nexport http_proxy="${url}"\nexport https_proxy="${url}"\nexport HTTP_PROXY="$http_proxy"\nexport HTTPS_PROXY="$https_proxy"\nexport no_proxy="localhost,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"\nexport NO_PROXY="$no_proxy"\n\n测试\n\ncurl -I https://www.google.com\napt update\nnpm ping\ndocker pull hello-world\n\nAPT 专用\n\ncat >/etc/apt/apt.conf.d/99proxy <<'EOF'\nAcquire::http::Proxy "${url}";\nAcquire::https::Proxy "${url}";\nEOF\n\n取消 APT\n\nrm -f /etc/apt/apt.conf.d/99proxy\n\nnpm 专用\n\nnpm config set proxy "${url}"\nnpm config set https-proxy "${url}"\n\n取消 npm\n\nnpm config delete proxy\nnpm config delete https-proxy\n\nDocker pull 专用\n\nmkdir -p /etc/systemd/system/docker.service.d\ncat >/etc/systemd/system/docker.service.d/http-proxy.conf <<'EOF'\n[Service]\nEnvironment="HTTP_PROXY=${url}"\nEnvironment="HTTPS_PROXY=${url}"\nEnvironment="NO_PROXY=localhost,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"\nEOF\nsystemctl daemon-reload\nsystemctl restart docker\n\n验证 Docker\n\nsystemctl show --property=Environment docker\ndocker pull hello-world\n\n取消 Docker\n\nrm -f /etc/systemd/system/docker.service.d/http-proxy.conf\nsystemctl daemon-reload\nsystemctl restart docker`;
}
function showProxyGuide(){
  const url = chainProxyUrl();
  if(!url){ out('暂无代理连接，请先识别 HTTP/SOCKS 入口并等待公网 IP 缓存。'); return; }
  writeLog(proxySetupGuide(url));
}
async function copyChainProxyUrl(btn){
  const url = chainProxyUrl();
  if(!url){ out('暂无可复制的 HTTP/SOCKS 代理连接，请先识别入口并等待公网 IP 缓存。'); return; }
  const old = btn ? btn.textContent : '复制';
  try{
    await copyText(url);
    if(btn) btn.textContent = '已复制';
    out(`已复制链式代理连接：${url}`);
  } catch(e){
    if(btn) btn.textContent = '复制失败';
    out(e);
  } finally {
    if(btn) setTimeout(() => { btn.textContent = old; }, 1500);
  }
}
function renderChainSummary(){
  const el = document.getElementById('chainSummary');
  if(!el) return;
  const entry = nodeSummary(state.chain && state.chain.entry, '入口');
  const nodes = (state.chain && state.chain.nodes) || [];
  const exitNode = nodeSummary(nodes.length ? nodes[nodes.length - 1] : null, '出口');
  const enabled = state.chain && state.chain.enabled !== false;
  const conn = document.getElementById('connectionText') ? document.getElementById('connectionText').textContent : '未测试';
  const proxyUrl = chainProxyUrl();
  const proxySub = proxyUrl ? `<div class="summary-sub" style="user-select:text">${escapeHtml(proxyUrl)}</div><button class="action-copy" style="margin-top:8px" onclick="copyChainProxyUrl(this)">复制代理连接</button><button class="action-copy" style="margin-top:8px; margin-left:6px" onclick="showProxyGuide()">使用教程</button>` : `<div class="summary-sub">${publicIp ? 'HTTP/SOCKS入口识别后显示' : '公网 IP 缓存中'}</div>`;
  el.innerHTML = `<div class="summary-card"><div class="summary-title">入口节点</div><div class="summary-value">${escapeHtml(entry.type)} · ${escapeHtml(entry.port)}</div><div class="summary-sub">${escapeHtml(entry.name)}</div></div>
    <div class="summary-card"><div class="summary-title">出口节点</div><div class="summary-value">${escapeHtml(exitNode.type)} · ${escapeHtml(exitNode.port)}</div><div class="summary-sub">${escapeHtml(exitNode.name)}</div></div>
    <div class="summary-card"><div class="summary-title">链式代理</div><div class="summary-value">${enabled ? '已启用' : '已停止'}</div><div class="summary-sub">${escapeHtml(conn)}</div></div>
    <div class="summary-card"><div class="summary-title">代理连接</div><div class="summary-value">${proxyUrl ? '可复制' : '等待入口'}</div>${proxySub}</div>`;
}
function renderChainSwitchVisual(isOn){
  const sw = document.getElementById('applySwitch');
  if(!sw) return;
  const wrap = sw.closest('.switch');
  if(!wrap) return;
  if(isOn) wrap.classList.add('on');
  else wrap.classList.remove('on');
}
function renderPerformanceSettings(settings){
  settings = settings || {};
  const values = {
    keep_alive: settings.keep_alive !== false,
    tcp_concurrent: settings.tcp_concurrent !== false,
    unified_delay: settings.unified_delay !== false,
    fake_ip: settings.fake_ip === true,
    split_route: settings.split_route !== false,
    ipv6: settings.ipv6 === true,
    connection_timeout: settings.connection_timeout || 5,
    log_level: settings.log_level || 'warning',
    tproxy: settings.tproxy === true
  };
  const map = {perfKeepAlive:'keep_alive', perfTcpConcurrent:'tcp_concurrent', perfUnifiedDelay:'unified_delay', perfFakeIp:'fake_ip', perfSplitRoute:'split_route', perfIpv6:'ipv6', perfTproxy:'tproxy'};
  Object.entries(map).forEach(([id, key]) => { const el = document.getElementById(id); if(el) el.checked = !!values[key]; });
  const timeout = document.getElementById('perfTimeout'); if(timeout) timeout.value = String(values.connection_timeout);
  const logLevel = document.getElementById('perfLogLevel'); if(logLevel) logLevel.value = values.log_level;
}
function collectPerformanceSettings(){
  return {
    keep_alive: !!document.getElementById('perfKeepAlive')?.checked,
    tcp_concurrent: !!document.getElementById('perfTcpConcurrent')?.checked,
    unified_delay: !!document.getElementById('perfUnifiedDelay')?.checked,
    fake_ip: !!document.getElementById('perfFakeIp')?.checked,
    split_route: !!document.getElementById('perfSplitRoute')?.checked,
    ipv6: !!document.getElementById('perfIpv6')?.checked,
    tproxy: !!document.getElementById('perfTproxy')?.checked,
    connection_timeout: Number(document.getElementById('perfTimeout')?.value || 5),
    log_level: document.getElementById('perfLogLevel')?.value || 'warning'
  };
}
function setPerformanceDisabled(disabled){
  ['perfKeepAlive','perfTcpConcurrent','perfUnifiedDelay','perfFakeIp','perfSplitRoute','perfIpv6','perfTproxy','perfTimeout','perfLogLevel'].forEach(id => { const el = document.getElementById(id); if(el) el.disabled = disabled; });
}
async function applyPerformanceSettings(){
  setPerformanceDisabled(true);
  out('正在应用性能优化配置，并热加载 mimo...');
  try{
    const data = await api('/api/performance', {settings: collectPerformanceSettings()});
    if(data.performance) renderPerformanceSettings(data.performance);
    out(data);
  } catch(e){
    out(e);
    await loadState(false);
  } finally {
    setPerformanceDisabled(false);
  }
}
function currentLocalServiceNames(){
  const names = [];
  (state.local_services || []).forEach(service => {
    const listener = service.listener || {};
    if(listener.name) names.push(String(listener.name));
    const text = service.listener_yaml || '';
    const match = text.match(/^\s*-?\s*name\s*:\s*['"]?([^'"\n#]+)['"]?/m);
    if(match && match[1]) names.push(match[1].trim());
  });
  return Array.from(new Set(names));
}
function currentLocalServicePorts(){
  const ports = [];
  (state.local_services || []).forEach(service => {
    const listener = service.listener || {};
    if(listener.port !== undefined && listener.port !== null) ports.push(Number(listener.port));
    const text = service.listener_yaml || '';
    const match = text.match(/^\s*-?\s*port\s*:\s*(\d+)/m);
    if(match && match[1]) ports.push(Number(match[1]));
  });
  return Array.from(new Set(ports.filter(Number.isFinite)));
}
function logPortChanges(changes){
  (changes || []).forEach(change => appendLog(`端口 ${change.requested} 已占用，已自动改为 ${change.assigned}`));
}
async function addLocalService(type){
  try{
    const data = await api('/api/parse/local-services', {yaml:LOCAL_EXAMPLES[type] || '', existing_names: currentLocalServiceNames(), existing_ports: currentLocalServicePorts()});
    data.services.forEach(service => service.enabled = false);
    state.local_services = (state.local_services || []).concat(data.services);
    renderLocalCards();
    logPortChanges(data.port_changes);
    await saveUiState(`已新增 ${data.services.length} 个服务端，默认关闭。`);
  } catch(e){ out(e); }
}
async function saveUiState(successMsg='状态已保存。'){
  const freshState = await collectFreshStateForSave();
  const data = await api('/api/save-state', {state:freshState});
  if(data.state) state = data.state;
  out(successMsg);
  return data;
}
function fillLocalExample(type){ document.getElementById('localPaste').value = LOCAL_EXAMPLES[type] || ''; }
function fillEntryExample(type){ const text = ENTRY_EXAMPLES[type] || ''; document.getElementById('entryText').value = text; state.chain.entry_text = text; }
function fillAnyTlsChainExample(){ state.chain.node_texts = [[ANYTLS_CHAIN_EXAMPLE]]; renderChainNodes(); }
function addChainNode(text=''){
  state.chain.node_texts = state.chain.node_texts || [['']];
  state.chain.node_texts.push([text || '']);
  renderChainNodes();
}

function localServiceStatus(svc){
  const listener = svc.listener || {};
  const managed = (state.managed && state.managed.listener_names) || [];
  if(svc.status) return svc.status;
  if(!svc.enabled) return {text:'未开启', cls:'', isOn:false};
  if(managed.includes(listener.name)) return {text:'已启动', cls:'on', isOn:true};
  return {text:'未启动', cls:'', isOn:false};
}
async function collectFreshStateForSave(){
  const latest = (await api('/api/state')).state || {version:1, local_services:[], chain:{enabled:false}, managed:{listener_names:[], proxy_names:[], proxy_group_names:[]}};
  document.querySelectorAll('#localCards .card textarea').forEach((ta, i) => { if(state.local_services[i]) { state.local_services[i].listener_yaml = ta.value; delete state.local_services[i].status; } });
  document.querySelectorAll('#localCards .card input[type="checkbox"]').forEach((cb, i) => { if(state.local_services[i]) state.local_services[i].enabled = cb.checked; });
  latest.local_services = JSON.parse(JSON.stringify(state.local_services || []));
  latest.chain = latest.chain || {enabled:false, entry_text:'', node_texts:[['']], entry:null, nodes:[]};
  const entryText = document.getElementById('entryText');
  if(entryText) latest.chain.entry_text = entryText.value;

  // 收集二维 node_texts
  const nodeLevels = [];
  document.querySelectorAll('#chainNodes > div').forEach(levelBox => {
    const levelNodes = [];
    levelBox.querySelectorAll('textarea').forEach(ta => {
      levelNodes.push(ta.value);
    });
    if(levelNodes.length > 0) nodeLevels.push(levelNodes);
  });
  if(nodeLevels.length > 0) latest.chain.node_texts = nodeLevels;

  return latest;
}
async function collectFreshLocalState(){
  return collectFreshStateForSave();
}
async function toggleLocalService(i, toggle){
  const svc = state.local_services[i];
  if(!svc) return;
  const checked = toggle.checked;
  const switchEl = toggle.closest('.switch');
  switchEl.classList.add('starting');
  switchEl.classList.remove('on');
  toggle.disabled = true;
  svc.enabled = checked;
  svc.status = checked ? {text:'启动中', cls:'pending'} : {text:'停止中', cls:'pending'};
  const statusEl = toggle.closest('.card').querySelector('.service-state');
  if(statusEl){ statusEl.textContent = svc.status.text; statusEl.className = 'service-state ' + svc.status.cls; }
  out(checked ? '正在保存 config.yaml，并热加载 mimo...' : '正在保存 config.yaml，并热加载 mimo...');
  try{
    const freshState = await collectFreshLocalState();
    freshState.local_services[i].enabled = checked;
    const data = await api('/api/apply', {state:freshState});
    out(data);
    applyReturnedState(data, {renderChain:false});
  } catch(e){
    out(e);
    if(state.local_services[i]) {
      state.local_services[i].enabled = false;
      state.local_services[i].status = {text:'无法启动', cls:'failed', isOn:false};
      renderLocalCards();
    }
  } finally {
    switchEl.classList.remove('starting');
    toggle.disabled = false;
  }
}
function renderLocalCards(){
  const el = document.getElementById('localCards'); el.innerHTML='';
  (state.local_services||[]).forEach((svc, i) => {
    const listener = svc.listener || {};
    const status = localServiceStatus(svc);
    const typeText = listener.type || '';
    const portText = listener.port !== undefined && listener.port !== null ? listener.port : '-';
    const summary = `${typeText || '未知协议'} · ${portText} · ${status.text}`;
    const card = document.createElement('div'); card.className='card';
    card.innerHTML = `<div class="card-head"><div class="card-title"><label class="switch ${status.isOn?'on':''}"><input type="checkbox" ${svc.enabled?'checked':''} onchange="toggleLocalService(${i}, this)"><span class="slider"></span></label><div><h3 style="margin:0">${escapeHtml(listener.name || svc.id || 'service')}</h3><div class="service-summary">${escapeHtml(summary)}</div><span class="service-state ${status.cls}">${status.text}</span></div></div><span class="pill">${escapeHtml(typeText)}</span></div>
      <div class="yaml-wrap"><label>节点全部信息</label><textarea oninput="state.local_services[${i}].listener_yaml=this.value">${escapeHtml(svc.listener_yaml || '')}</textarea></div>
      <div class="card-actions"><button class="action-copy" onclick="copyLocalNode(${i}, this)">复制节点</button><button class="action-copy" onclick="copyLocalNodeUrl(${i}, this)">复制节点URL</button><button class="action-danger" onclick="removeLocal(${i})">删除</button></div>`;
    el.appendChild(card);
  });
  initUndoForTextControls(el);
}
async function copyText(text){
  if(navigator.clipboard && window.isSecureContext){
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
}
async function copyLocalNode(i, btn){
  if(!state.local_services[i]) return;
  const oldText = btn ? btn.textContent : '复制节点';
  if(btn){ btn.disabled = true; btn.textContent = '复制中...'; }
  const textareas = document.querySelectorAll('#localCards .card textarea');
  if(textareas[i]) state.local_services[i].listener_yaml = textareas[i].value;
  try{
    const data = await api('/api/local-node', {service:state.local_services[i]});
    await copyText(data.yaml);
    if(btn) btn.textContent = '已复制';
    out(`已复制，公网 IP：${data.public_ip}`);
  } catch(e){
    if(btn) btn.textContent = '复制失败';
    out(e);
  } finally {
    if(btn){
      setTimeout(() => { btn.disabled = false; btn.textContent = oldText; }, 1500);
    }
  }
}
async function copyLocalNodeUrl(i, btn){
  if(!state.local_services[i]) return;
  const oldText = btn ? btn.textContent : '复制节点URL';
  if(btn){ btn.disabled = true; btn.textContent = '复制中...'; }
  const textareas = document.querySelectorAll('#localCards .card textarea');
  if(textareas[i]) state.local_services[i].listener_yaml = textareas[i].value;
  try{
    const data = await api('/api/local-node-url', {service:state.local_services[i]});
    await copyText(data.url);
    if(btn) btn.textContent = '已复制';
    out(`已复制节点URL，公网 IP：${data.public_ip}`);
  } catch(e){
    if(btn) btn.textContent = '复制失败';
    out(e);
  } finally {
    if(btn){
      setTimeout(() => { btn.disabled = false; btn.textContent = oldText; }, 1500);
    }
  }
}
async function removeLocal(i){
  if(!state.local_services[i]) return;
  document.querySelectorAll('#localCards .card textarea').forEach((ta, index) => { if(state.local_services[index]) state.local_services[index].listener_yaml = ta.value; });
  state.local_services[i].enabled = false;
  state.local_services[i].status = {text:'停止中', cls:'pending', isOn:false};
  out('正在删除本地服务端、保存 config.yaml，并热加载 mimo...');
  state.local_services.splice(i, 1);
  renderLocalCards();
  try{
    const freshState = await collectFreshLocalState();
    const data = await api('/api/apply', {state:freshState});
    out(data);
    applyReturnedState(data, {renderChain:false});
  } catch(e){
    out(e);
    renderLocalCards();
  }
}
function yamlField(text, key){
  const safeKey = String(key).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const prefix = new RegExp('^\\s*-?\\s*' + safeKey + '\\s*:');
  for(const line of String(text || '').split('\n')){
    if(!prefix.test(line)) continue;
    return line.replace(prefix, '').replace(/\s+#.*$/, '').trim().replace(/^['"]|['"]$/g, '');
  }
  return '';
}
function chainNodeInfo(text){
  const type = yamlField(text, 'type') || '未知协议';
  const port = yamlField(text, 'port') || '-';
  const name = yamlField(text, 'name') || yamlField(text, 'server') || '未命名节点';
  return `${type} · ${port} · ${name}`;
}
function renderChainNodes(){
  const el = document.getElementById('chainNodes'); el.innerHTML='';
  const nodeLevels = state.chain.node_texts || [['']];

  nodeLevels.forEach((levelNodes, levelIndex) => {
    // 级别容器
    const levelBox = document.createElement('div');
    levelBox.style.cssText = 'margin-bottom:16px;';

    const levelHeader = document.createElement('div');
    levelHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;';
    levelHeader.innerHTML = `
      <h3 style="margin:0;font-size:15px;color:#2c5282;">第${levelIndex+2}级节点</h3>
      <div style="display:flex;gap:8px;">
        <button class="action-copy" onclick="addBackupNode(${levelIndex})" title="添加备用节点">+ 备用</button>
        <button class="action-add" onclick="addChainNode()">+ 增加下一级</button>
        <button class="action-danger" onclick="removeChainLevel(${levelIndex})">删除本级</button>
      </div>
    `;
    levelBox.appendChild(levelHeader);

    // 同级节点卡片
    levelNodes.forEach((nodeYaml, nodeIndex) => {
      const card = document.createElement('div');
      card.className = 'card';
      card.style.cssText = 'margin-bottom:8px;';

      const nodeLabel = levelNodes.length > 1 ? `<span class="muted" style="font-size:12px;">节点 ${nodeIndex+1}${nodeIndex === 0 ? ' (主)' : ' (备用)'}</span>` : '';
      const deleteBtn = levelNodes.length > 1 ? `<button class="action-danger" onclick="removeBackupNode(${levelIndex}, ${nodeIndex})" style="font-size:12px;padding:4px 8px;">删除</button>` : '';

      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          ${nodeLabel}
          ${deleteBtn}
        </div>
        <div class="yaml-wrap">
          <textarea data-level="${levelIndex}" data-node="${nodeIndex}" oninput="updateNodeText(${levelIndex}, ${nodeIndex}, this.value)">${escapeHtml(nodeYaml)}</textarea>
        </div>
      `;
      levelBox.appendChild(card);
    });

    el.appendChild(levelBox);
  });

  initUndoForTextControls(el);
}
function updateNodeText(levelIndex, nodeIndex, value){
  if(!state.chain.node_texts[levelIndex]) state.chain.node_texts[levelIndex] = [];
  state.chain.node_texts[levelIndex][nodeIndex] = value;
}
function addBackupNode(levelIndex){
  if(!state.chain.node_texts[levelIndex]) state.chain.node_texts[levelIndex] = [''];

  const firstNode = state.chain.node_texts[levelIndex][0] || '';
  let template = '';

  if(firstNode.trim()){
    const nameMatch = firstNode.match(/name:\s*(\S+)/);
    const typeMatch = firstNode.match(/type:\s*(\S+)/);
    const serverMatch = firstNode.match(/server:\s*(\S+)/);
    const portMatch = firstNode.match(/port:\s*(\d+)/);
    const cipherMatch = firstNode.match(/cipher:\s*(\S+)/);

    const baseName = nameMatch ? nameMatch[1].replace(/-(main|backup\d*)$/i, '') : 'chain-node';
    const backupCount = state.chain.node_texts[levelIndex].length;

    template = `- name: ${baseName}-backup${backupCount}
  type: ${typeMatch ? typeMatch[1] : 'ss'}
  server: 备用服务器IP
  port: ${portMatch ? portMatch[1] : '18000'}
  cipher: ${cipherMatch ? cipherMatch[1] : 'aes-128-gcm'}
  password: 备用密码
  udp: true`;
  } else {
    template = `- name: chain-level${levelIndex+2}-backup1
  type: ss
  server: 备用服务器IP
  port: 18000
  cipher: aes-128-gcm
  password: 备用密码
  udp: true`;
  }

  state.chain.node_texts[levelIndex].push(template);
  renderChainNodes();
}
function removeBackupNode(levelIndex, nodeIndex){
  if(state.chain.node_texts[levelIndex] && state.chain.node_texts[levelIndex].length > 1){
    state.chain.node_texts[levelIndex].splice(nodeIndex, 1);
    renderChainNodes();
  }
}
function removeChainLevel(levelIndex){
  state.chain.node_texts.splice(levelIndex, 1);
  if(state.chain.node_texts.length === 0) state.chain.node_texts = [['']];
  renderChainNodes();
}
async function removeChainNode(i){
  // 已废弃，由 removeChainLevel 替代
  removeChainLevel(i);
}
function renderChainPreview(){
  const p = document.getElementById('chainPreview');
  if(!state.chain.entry && !(state.chain.nodes||[]).length){ p.textContent='尚未生成链路预览。'; renderChainSummary(); return; }
  p.textContent = JSON.stringify({enabled:state.chain.enabled, entry:state.chain.entry, mode:'dialer-proxy', exit_proxy:state.chain.exit_proxy, nodes:state.chain.nodes}, null, 2);
  renderChainSummary();
}
function applyReturnedState(data, options={}){
  if(data.state) state = data.state;
  else if(data.next_state) state = data.next_state;
  if(data.public_ip) publicIp = data.public_ip;
  if(!state.chain) state.chain = {enabled:false, entry_text:'', node_texts:[['']]};

  // 兼容旧格式：node_texts = ['str'] → [['str']]
  if(state.chain.node_texts && state.chain.node_texts.length > 0){
    if(typeof state.chain.node_texts[0] === 'string'){
      state.chain.node_texts = state.chain.node_texts.map(txt => [txt]);
    }
  }

  document.getElementById('statusPill').textContent = data.container || document.getElementById('statusPill').textContent || '未知';
  const applySwitch = document.getElementById('applySwitch');
  const applySwitchText = document.getElementById('applySwitchText');
  if(applySwitch && options.syncSwitch !== false){
    applySwitch.checked = state.chain.enabled !== false;
    applySwitchText.textContent = applySwitch.checked ? '已应用' : '应用当前配置';
    renderChainSwitchVisual(applySwitch.checked);
  }
  if(options.renderLocal !== false) renderLocalCards();
  if(options.renderChain !== false){ renderChainNodes(); renderChainPreview(); }
}
async function loadState(showConnectivity=false){
  try{
    const data = await api('/api/state'); state = data.state; if(data.public_ip) publicIp = data.public_ip; if(!state.chain) state.chain={enabled:true,node_texts:[['']]};

    // 兼容旧格式：node_texts = ['str'] → [['str']]
    if(state.chain.node_texts && state.chain.node_texts.length > 0){
      if(typeof state.chain.node_texts[0] === 'string'){
        state.chain.node_texts = state.chain.node_texts.map(txt => [txt]);
      }
    }

    document.getElementById('entryText').value = state.chain.entry_text || '';
    const applySwitch = document.getElementById('applySwitch');
    const applySwitchText = document.getElementById('applySwitchText');
    if(applySwitch){
      applySwitch.checked = state.chain.enabled !== false;
      applySwitchText.textContent = applySwitch.checked ? '已应用' : '应用当前配置';
      renderChainSwitchVisual(state.chain.enabled !== false);
    }
    document.getElementById('statusPill').textContent = data.container || '未知';
    renderPerformanceSettings(data.performance || {});
    const conn = data.connectivity;
    if(!state.chain.enabled){ setConnectionStatus('unknown', '已停止', ''); }
    else if(conn && conn.ok){ setConnectionStatus('connected', connectivityBadgeText(conn), connectivityDetail(conn)); }
    else if(conn && conn.checked_at){ setConnectionStatus('failed', connectivityBadgeText(conn), connectivityDetail(conn)); }
    else { setConnectionStatus('unknown', '未测试', ''); }
    renderLocalCards(); renderChainNodes(); renderChainPreview();
  }catch(e){ out(e); }
}
async function parseLocal(){
  try{ const data = await api('/api/parse/local-services', {yaml:document.getElementById('localPaste').value, existing_names: currentLocalServiceNames(), existing_ports: currentLocalServicePorts()}); state.local_services = (state.local_services||[]).concat(data.services); renderLocalCards(); logPortChanges(data.port_changes); await saveUiState(`识别到 ${data.services.length} 个服务。`); }
  catch(e){ out(e); }
}
async function parseChain(){
  try{
    state.chain.enabled = document.getElementById('applySwitch') ? document.getElementById('applySwitch').checked : true;
    state.chain.entry_text = document.getElementById('entryText').value;
    const data = await api('/api/parse/chain', {entry_yaml:state.chain.entry_text, node_yamls:state.chain.node_texts || []});
    state.chain.entry = data.entry; state.chain.nodes = data.nodes; state.chain.exit_proxy = data.exit_proxy; delete state.chain.group_name; renderChainPreview(); out('链路识别完成。');
  }catch(e){ out(e); }
}
async function collectFreshState(){
  document.querySelectorAll('#localCards .card textarea').forEach((ta, i) => { if(state.local_services[i]) state.local_services[i].listener_yaml = ta.value; });
  document.querySelectorAll('#localCards .card input[type="checkbox"]').forEach((cb, i) => { if(state.local_services[i]) state.local_services[i].enabled = cb.checked; });
  state.chain.enabled = document.getElementById('applySwitch') ? document.getElementById('applySwitch').checked : true;
  state.chain.entry_text = document.getElementById('entryText').value;

  // 收集二维 node_texts
  const nodeLevels = [];
  document.querySelectorAll('#chainNodes > div').forEach(levelBox => {
    const levelNodes = [];
    levelBox.querySelectorAll('textarea').forEach(ta => levelNodes.push(ta.value));
    if(levelNodes.length > 0) nodeLevels.push(levelNodes);
  });
  state.chain.node_texts = nodeLevels;

  // 扁平化传给 API
  const flatNodeYamls = nodeLevels.flatMap(level => level.filter(n => n.trim()));

  if(state.chain.entry_text.trim() && flatNodeYamls.length > 0){
    const data = await api('/api/parse/chain', {entry_yaml:state.chain.entry_text, node_yamls:flatNodeYamls});
    state.chain.entry = data.entry; state.chain.nodes = data.nodes; state.chain.exit_proxy = data.exit_proxy; delete state.chain.group_name; renderChainPreview();
  } else {
    state.chain.entry = null; state.chain.nodes = []; state.chain.exit_proxy = ''; renderChainPreview();
  }
  return JSON.parse(JSON.stringify(state));
}
async function collectFreshChainState(){
  const latest = (await api('/api/state')).state || {version:1, local_services:[], managed:{listener_names:[], proxy_names:[], proxy_group_names:[]}};
  latest.chain = latest.chain || {enabled:true, entry_text:'', node_texts:[['']], entry:null, nodes:[]};
  latest.chain.enabled = document.getElementById('applySwitch') ? document.getElementById('applySwitch').checked : true;
  latest.chain.entry_text = document.getElementById('entryText').value;

  // 收集二维 node_texts
  const nodeLevels = [];
  document.querySelectorAll('#chainNodes > div').forEach(levelBox => {
    const levelNodes = [];
    levelBox.querySelectorAll('textarea').forEach(ta => levelNodes.push(ta.value));
    if(levelNodes.length > 0) nodeLevels.push(levelNodes);
  });
  latest.chain.node_texts = nodeLevels;

  // 扁平化传给 API
  const flatNodeYamls = nodeLevels.flatMap(level => level.filter(n => n.trim()));

  if(latest.chain.entry_text.trim() && flatNodeYamls.length > 0){
    const data = await api('/api/parse/chain', {entry_yaml:latest.chain.entry_text, node_yamls:flatNodeYamls});
    latest.chain.entry = data.entry; latest.chain.nodes = data.nodes; latest.chain.exit_proxy = data.exit_proxy; delete latest.chain.group_name;
    state.chain = latest.chain; renderChainPreview();
  } else {
    latest.chain.entry = null; latest.chain.nodes = []; latest.chain.exit_proxy = ''; state.chain = latest.chain; renderChainPreview();
  }
  return JSON.parse(JSON.stringify(latest));
}
async function testConnectivityOnly(btn){
  // 检查链式代理是否启用
  const sw = document.getElementById('applySwitch');
  if(!sw || !sw.checked){
    appendLog('⚠️ 链式代理未启用，测试将使用 direct 模式（直连）。如需测试链式代理，请先打开开关并应用配置。');
  }

  btn.disabled = true;
  btn.classList.remove('success', 'failed');
  setConnectionStatus('testing', '检测中', '700ms 超时，重试 1 次');
  try{
    const data = await api('/api/connectivity-test', {});
    const conn = data.connectivity;
    appendLog(connectivityLogLine(conn));
    if(conn && conn.ok){
      btn.classList.add('success');
      setConnectionStatus('connected', connectivityBadgeText(conn), connectivityDetail(conn));
    } else {
      btn.classList.add('failed');
      setConnectionStatus('failed', connectivityBadgeText(conn), connectivityDetail(conn));
    }
  } catch(e){
    appendLog(e);
    btn.classList.add('failed');
    setConnectionStatus('failed', '执行失败', e && e.error ? e.error : '请求失败');
  } finally {
    btn.disabled = false;
    setTimeout(() => { btn.classList.remove('success', 'failed'); }, 3000);
  }
}
async function validateOnly(){
  const btn = document.getElementById('validateBtn');
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = '校验中...'; out('正在清理页面缓存并仅使用当前链式代理参数校验...');
  try{ const freshState = await collectFreshChainState(); const data = await api('/api/validate', {state:freshState}); out(data); }
  catch(e){ out(e); }
  finally{ btn.disabled = false; btn.textContent = old; }
}
async function applyConfig(toggle){
  const sw = toggle || document.getElementById('applySwitch');
  const label = document.getElementById('applySwitchText');
  const targetOn = sw.checked;
  const switchEl = sw.closest('.switch');
  switchEl.classList.add('starting');
  switchEl.classList.remove('on');
  sw.disabled = true;
  label.textContent = targetOn ? '应用中...' : '停止中...';
  setConnectionStatus('testing', '检测中', targetOn ? '正在测试 google.com 连通性' : '正在停止链式代理');
  out(targetOn ? '正在保存 config.yaml，热加载 mimo，并测试 google.com 连通性...' : '正在保存 config.yaml，关闭当前链式代理，并热加载 mimo...');
  try{
    const freshState = await collectFreshChainState();
    freshState.chain.enabled = targetOn;
    const data = await api('/api/apply', {state:freshState});
    out(data);
    applyReturnedState(data, {syncSwitch:false});
    label.textContent = targetOn ? '已应用' : '已停止';
    const conn = data.connectivity;
    if(targetOn && conn && conn.ok){
      setConnectionStatus('connected', connectivityBadgeText(conn), connectivityDetail(conn));
      sw.checked = true;
      renderChainSwitchVisual(true);
    } else if(targetOn) {
      setConnectionStatus('failed', connectivityBadgeText(conn), connectivityDetail(conn));
      sw.checked = true;
      renderChainSwitchVisual(true);
    } else {
      setConnectionStatus('unknown', '已停止', '');
      sw.checked = false;
      renderChainSwitchVisual(false);
    }
  }
  catch(e){
    out(e);
    label.textContent = targetOn ? '应用失败' : '停止失败';
    sw.checked = !targetOn;
    setConnectionStatus('failed', '执行失败', e && e.error ? e.error : '请求失败');
    renderChainSwitchVisual(false);
  }
  finally{
    setTimeout(() => {
      switchEl.classList.remove('starting');
      sw.disabled = false;
      label.textContent = sw.checked ? '已应用' : '应用当前配置';
    }, 1500);
  }
}
initUndoForTextControls();
loadState();
</script>
</body>
</html>
"""


def load_yaml(path, default):
    if not path.exists() or path.stat().st_size == 0:
        return copy.deepcopy(default)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return copy.deepcopy(default) if data is None else data


def save_yaml_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def save_config_in_place(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    with path.open("w", encoding="utf-8") as f:
        f.write(content)
        f.truncate()
        f.flush()
        os.fsync(f.fileno())


def command_result(cmd, timeout=120):
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return {"ok": p.returncode == 0, "returncode": p.returncode, "output": p.stdout}


def container_status():
    try:
        active = command_result(["systemctl", "is-active", MIMO_SERVICE_NAME], 10)["output"].strip()
        pid = command_result(["systemctl", "show", "-p", "MainPID", "--value", MIMO_SERVICE_NAME], 10)["output"].strip()
        return f"{MIMO_SERVICE_NAME} {active or 'unknown'} PID {pid or '0'}"
    except Exception as e:
        return f"状态获取失败：{e}"


def clean_yaml_text(text):
    text = text.replace("\t", "  ").strip("\n")
    lines = text.splitlines()
    nonempty = [ln for ln in lines if ln.strip()]
    if not nonempty:
        return text
    min_indent = min(len(ln) - len(ln.lstrip()) for ln in nonempty)
    if min_indent:
        lines = [ln[min_indent:] if len(ln) >= min_indent else ln for ln in lines]
    fixed = []
    top_list = any(re.match(r"^\s*-\s+", ln) for ln in lines)
    for ln in lines:
        if top_list and re.match(r"^\s{4,}\S", ln):
            ln = ln[2:]
        fixed.append(ln.rstrip())
    return "\n".join(fixed).strip()


def parse_yaml_snippet(text):
    if not text or not text.strip():
        return []
    attempts = [text, clean_yaml_text(text)]
    last_error = None
    for candidate in attempts:
        try:
            parsed = yaml.safe_load(candidate)
            return normalize_node_list(parsed)
        except Exception as e:
            last_error = e
    raise ValueError(f"YAML 解析失败：{last_error}")


def normalize_node_list(parsed):
    if parsed is None:
        return []
    if isinstance(parsed, dict):
        for key in ("proxies", "mihomo-proxies", "listeners", "items"):
            if key in parsed:
                return normalize_node_list(parsed[key])
        return [parsed]
    if isinstance(parsed, list):
        items = []
        for item in parsed:
            if not isinstance(item, dict):
                raise ValueError("列表中包含非对象项目")
            items.append(item)
        return items
    raise ValueError("YAML 顶层必须是对象或列表")


def slug(value):
    value = str(value or "item").strip()
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^0-9A-Za-z_.\-一-鿿]", "-", value)
    return value or "item"


def generated_listener_name(listener, used_names=None):
    used_names = {str(name) for name in (used_names or set()) if name}
    listen = listener.get("listen") or listener.get("server") or "0.0.0.0"
    typ = listener.get("type") or "listener"
    for _ in range(20):
        name = slug(f"{typ}-{listen}-{secrets.token_hex(3)}")
        if name not in used_names:
            return name
    return slug(f"{typ}-{listen}-{secrets.token_hex(8)}")


def listener_to_card(listener, used_names=None):
    if not listener.get("name"):
        listener["name"] = generated_listener_name(listener, used_names)
    return {
        "id": slug(listener.get("name")),
        "enabled": False,
        "listener": listener,
        "listener_yaml": yaml.safe_dump(listener, allow_unicode=True, sort_keys=False).strip(),
    }


def proxy_snippet_to_listener(node, used_names=None, used_ports=None):
    typ = str(node.get("type", "")).lower()
    port = int(node.get("port")) if node.get("port") is not None else None
    listen = node.get("listen") or node.get("server") or "0.0.0.0"
    name = node.get("name") or generated_listener_name({"type": typ, "listen": listen}, used_names)
    if not port:
        raise ValueError(f"{name} 缺少 port")
    port = next_available_port(port, used_ports)
    if typ == "tuic":
        uuid = node.get("uuid")
        password = node.get("password")
        if not uuid or not password:
            raise ValueError(f"{name} 缺少 uuid/password")
        listener = {
            "name": name,
            "type": "tuic",
            "listen": "0.0.0.0",
            "port": port,
            "users": {str(uuid): str(password)},
            "certificate": CERT_PATH,
            "private-key": KEY_PATH,
            "congestion-controller": node.get("congestion-controller") or node.get("congestion_controller") or "bbr",
            "max-idle-time": node.get("max-idle-time", 30000),
            "authentication-timeout": node.get("authentication-timeout", 2000),
            "alpn": node.get("alpn") or ["h3"],
            "max-udp-relay-packet-size": node.get("max-udp-relay-packet-size", 1400),
        }
        return listener
    if typ == "hysteria2":
        password = node.get("password")
        if not password:
            raise ValueError(f"{name} 缺少 password")
        username = node.get("username") or node.get("user") or "mimo"
        return {
            "name": name,
            "type": "hysteria2",
            "listen": node.get("listen") or node.get("server") or "0.0.0.0",
            "port": port,
            "users": {str(username): str(password)},
            "up": node.get("up", "200 Mbps"),
            "down": node.get("down", "200 Mbps"),
            "ignore-client-bandwidth": bool(node.get("ignore-client-bandwidth", False)),
            "obfs": node.get("obfs", "salamander"),
            "obfs-password": node.get("obfs-password") or node.get("obfs_password") or HYSTERIA2_OBFS_PASSWORD,
            "masquerade": node.get("masquerade", ""),
            "alpn": node.get("alpn") or ["h3"],
            "certificate": CERT_PATH,
            "private-key": KEY_PATH,
        }
    if typ == "anytls":
        password = node.get("password")
        if not password:
            raise ValueError(f"{name} 缺少 password")
        username = node.get("username") or node.get("user") or "mimo"
        return {
            "name": name,
            "type": "anytls",
            "listen": "0.0.0.0",
            "port": port,
            "users": {str(username): str(password)},
            "certificate": CERT_PATH,
            "private-key": KEY_PATH,
            "padding-scheme": node.get("padding-scheme", ""),
        }
    if typ in ("ss", "shadowsocks"):
        cipher = node.get("cipher")
        password = node.get("password")
        if not cipher or not password:
            raise ValueError(f"{name} 缺少 cipher/password")
        return {
            "name": name,
            "type": "shadowsocks",
            "listen": node.get("listen") or node.get("server") or "0.0.0.0",
            "port": port,
            "cipher": cipher,
            "password": password,
            "udp": bool(node.get("udp", True)),
        }
    if typ in ("http", "socks", "socks5"):
        listener = {
            "name": name,
            "type": "socks" if typ == "socks5" else typ,
            "listen": node.get("listen") or node.get("server") or "0.0.0.0",
            "port": port,
        }
        username = node.get("username")
        password = node.get("password")
        if username or password:
            listener["users"] = [{"username": username or "", "password": password or ""}]
        if typ in ("socks", "socks5"):
            listener["udp"] = bool(node.get("udp", True))
        return listener
    raise ValueError(f"暂不支持转换为本地服务端的类型：{typ or '未知'}")


def fetch_public_ip():
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            result = command_result(["curl", "-fsSL", "--max-time", "4", url], 8)
            ip = result.get("output", "").strip().splitlines()[0] if result.get("output") else ""
            if result.get("ok") and re.match(r"^[0-9A-Fa-f:.]+$", ip):
                return ip
        except Exception:
            pass
    raise ValueError("获取公网 IP 失败")


def refresh_public_ip_cache(force=False):
    with IP_CACHE_LOCK:
        if IP_CACHE["refreshing"]:
            return
        if not force and IP_CACHE["ip"] and time.time() - IP_CACHE["updated_at"] < 1800:
            return
        IP_CACHE["refreshing"] = True
    try:
        ip = fetch_public_ip()
        with IP_CACHE_LOCK:
            IP_CACHE.update({"ip": ip, "updated_at": time.time(), "error": ""})
    except Exception as e:
        with IP_CACHE_LOCK:
            IP_CACHE["error"] = str(e)
    finally:
        with IP_CACHE_LOCK:
            IP_CACHE["refreshing"] = False


def refresh_public_ip_cache_async(force=False):
    with IP_CACHE_LOCK:
        if IP_CACHE["refreshing"]:
            return
        if not force and IP_CACHE["ip"] and time.time() - IP_CACHE["updated_at"] < 1800:
            return
    threading.Thread(target=refresh_public_ip_cache, kwargs={"force": force}, daemon=True).start()


def public_ip_cached():
    with IP_CACHE_LOCK:
        ip = IP_CACHE["ip"]
        age = time.time() - IP_CACHE["updated_at"] if IP_CACHE["updated_at"] else None
    if ip:
        if age is not None and age > 1800:
            refresh_public_ip_cache_async(force=True)
        return ip, True
    refresh_public_ip_cache(force=True)
    with IP_CACHE_LOCK:
        if IP_CACHE["ip"]:
            return IP_CACHE["ip"], False
        error = IP_CACHE["error"]
    raise ValueError(error or "获取公网 IP 失败")


def public_ip():
    ip, _ = public_ip_cached()
    return ip


def b64url_no_pad(text):
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def query_string(params):
    return urlencode({k: v for k, v in params.items() if v is not None and v != ""}, doseq=True)


def listener_to_client_node(listener, server_ip):
    typ = str(listener.get("type", "")).lower()
    node = {"name": listener.get("name"), "type": "ss" if typ == "shadowsocks" else typ, "server": server_ip, "port": int(listener.get("port"))}
    if typ == "tuic":
        users = listener.get("users") or {}
        if not isinstance(users, dict) or not users:
            raise ValueError("TUIC listener 缺少 users")
        uuid, password = next(iter(users.items()))
        node.update({
            "uuid": str(uuid),
            "password": str(password),
            "sni": listener.get("sni") or "www.sciencedirect.com",
            "alpn": listener.get("alpn") or ["h3"],
            "skip-cert-verify": True,
            "disable-sni": bool(listener.get("disable-sni", False)),
            "congestion-controller": listener.get("congestion-controller", "bbr"),
            "udp": True,
        })
    elif typ == "hysteria2":
        users = listener.get("users") or {}
        password = None
        if isinstance(users, dict) and users:
            password = next(iter(users.values()))
        if not password:
            raise ValueError("Hysteria2 listener 缺少 users/password")
        node.update({
            "password": str(password),
            "obfs": listener.get("obfs", "salamander"),
            "obfs-password": listener.get("obfs-password") or HYSTERIA2_OBFS_PASSWORD,
            "sni": listener.get("sni", ""),
            "alpn": listener.get("alpn") or ["h3"],
            "skip-cert-verify": True,
            "udp": True,
        })
    elif typ == "anytls":
        users = listener.get("users") or {}
        password = None
        if isinstance(users, dict) and users:
            password = next(iter(users.values()))
        if not password:
            raise ValueError("AnyTLS listener 缺少 users/password")
        node.update({
            "password": str(password),
            "sni": listener.get("sni", ""),
            "alpn": listener.get("alpn") or ["h2", "http/1.1"],
            "skip-cert-verify": True,
            "client-fingerprint": listener.get("client-fingerprint", "chrome"),
            "udp": True,
        })
    elif typ == "shadowsocks":
        node.update({"cipher": listener.get("cipher"), "password": listener.get("password"), "udp": bool(listener.get("udp", True))})
    elif typ in ("http", "socks"):
        users = listener.get("users") or []
        if isinstance(users, list) and users:
            node["username"] = users[0].get("username", "")
            node["password"] = users[0].get("password", "")
        if typ == "socks":
            node["udp"] = bool(listener.get("udp", True))
    else:
        raise ValueError(f"暂不支持复制节点类型：{typ or '未知'}")
    return yaml.safe_dump([node], allow_unicode=True, sort_keys=False).strip()


def listener_to_client_url(listener, server_ip):
    typ = str(listener.get("type", "")).lower()
    name = str(listener.get("name") or typ or "node")
    tag = quote(name, safe="")
    host = str(server_ip)
    port = int(listener.get("port"))
    if typ == "shadowsocks":
        cipher = str(listener.get("cipher") or "")
        password = str(listener.get("password") or "")
        if not cipher or not password:
            raise ValueError("Shadowsocks listener 缺少 cipher/password")
        userinfo = b64url_no_pad(f"{cipher}:{password}")
        return f"ss://{userinfo}@{host}:{port}#{tag}"
    if typ == "hysteria2":
        users = listener.get("users") or {}
        password = str(next(iter(users.values()))) if isinstance(users, dict) and users else ""
        if not password:
            raise ValueError("Hysteria2 listener 缺少 users/password")
        params = {
            "sni": listener.get("sni") or None,
            "insecure": "1",
            "obfs": listener.get("obfs") or None,
            "obfs-password": listener.get("obfs-password") or None,
        }
        qs = query_string(params)
        return f"hysteria2://{quote(password, safe='')}@{host}:{port}/?{qs}#{tag}"
    if typ == "tuic":
        users = listener.get("users") or {}
        if not isinstance(users, dict) or not users:
            raise ValueError("TUIC listener 缺少 users")
        uuid, password = next(iter(users.items()))
        params = {
            "congestion_control": listener.get("congestion-controller") or "bbr",
            "alpn": ",".join(listener.get("alpn") or ["h3"]),
            "sni": listener.get("sni") or "www.sciencedirect.com",
            "allow_insecure": "1",
            "disable_sni": "1" if listener.get("disable-sni") else "0",
            "udp_relay_mode": listener.get("udp-relay-mode") or "native",
        }
        return f"tuic://{quote(str(uuid), safe='')}:{quote(str(password), safe='')}@{host}:{port}?{query_string(params)}#{tag}"
    if typ == "anytls":
        users = listener.get("users") or {}
        password = str(next(iter(users.values()))) if isinstance(users, dict) and users else ""
        if not password:
            raise ValueError("AnyTLS listener 缺少 users/password")
        params = {"sni": listener.get("sni") or None, "insecure": "1"}
        return f"anytls://{quote(password, safe='')}@{host}:{port}/?{query_string(params)}#{tag}"
    if typ in ("http", "socks"):
        users = listener.get("users") or []
        auth = ""
        if isinstance(users, list) and users:
            username = quote(str(users[0].get("username", "")), safe="")
            password = quote(str(users[0].get("password", "")), safe="")
            auth = f"{username}:{password}@"
        scheme = "socks5" if typ == "socks" else "http"
        return f"{scheme}://{auth}{host}:{port}#{tag}"
    raise ValueError(f"暂不支持复制节点URL类型：{typ or '未知'}")


def normalize_entry_listener(text):
    nodes = parse_yaml_snippet(text)
    if len(nodes) != 1:
        raise ValueError("入口 Inbound 只能填写一个对象")
    entry = copy.deepcopy(nodes[0])
    if "listen" not in entry and "server" in entry:
        entry["listen"] = entry.pop("server")
    entry.setdefault("listen", "0.0.0.0")
    if "port" not in entry:
        raise ValueError("入口缺少 port")
    entry["port"] = int(entry["port"])
    typ = str(entry.get("type", "")).lower()
    if typ == "ss":
        entry["type"] = "shadowsocks"
    if typ == "socks5":
        entry["type"] = "socks"
    if str(entry.get("type", "")).lower() in ("http", "socks") and ("username" in entry or "password" in entry):
        username = entry.pop("username", "")
        password = entry.pop("password", "")
        entry["users"] = [] if not username and not password else [{"username": username, "password": password}]
    entry.setdefault("name", f"entry-{entry.get('type','in')}-{entry['port']}")
    return entry


def normalize_chain_nodes(texts):
    """解析链式节点，支持同级多节点自动生成 urltest 组

    支持格式：
    - 旧格式：['yaml1', 'yaml2']  # 每个字符串代表一级
    - 新格式：[['yaml1', 'backup1'], ['yaml2']]  # 二维数组，支持同级备用
    """
    nodes = []
    levels = []  # 每一级的节点列表

    # 兼容旧格式：如果是字符串列表，转换为二维数组
    if texts and isinstance(texts[0], str):
        texts = [[t] for t in texts]

    for level_texts in texts:
        # level_texts 是列表，包含该级别的所有节点 YAML
        level_nodes = []

        # 确保是列表
        if isinstance(level_texts, str):
            level_texts = [level_texts]

        for text in level_texts:
            if text and text.strip():
                for node in parse_yaml_snippet(text):
                    if "name" not in node or "type" not in node:
                        raise ValueError("链路节点必须包含 name 和 type")

                    # 修正常见错误：proxy 节点使用 listen 而不是 server
                    if "listen" in node and "server" not in node:
                        node["server"] = node.pop("listen")

                    # 修正类型名称：shadowsocks → ss
                    if node.get("type") == "shadowsocks":
                        node["type"] = "ss"

                    level_nodes.append(node)

        if level_nodes:
            levels.append(level_nodes)

    if not levels:
        raise ValueError("至少需要一个第二级节点")

    # 扁平化所有节点
    for level in levels:
        nodes.extend(level)

    return nodes, levels


def parse_listener_yaml(service, used_names=None):
    text = service.get("listener_yaml")
    if text and text.strip():
        nodes = parse_yaml_snippet(text)
        if len(nodes) != 1:
            raise ValueError("每个服务卡片只能包含一个 listener")
        listener = nodes[0]
    else:
        listener = copy.deepcopy(service.get("listener") or {})
    if "type" not in listener or "port" not in listener:
        raise ValueError("服务 listener 必须包含 type/port")
    listener["port"] = int(listener["port"])
    listener.setdefault("listen", listener.get("server") or "0.0.0.0")
    if not listener.get("name"):
        listener["name"] = generated_listener_name(listener, used_names)
        service["listener"] = listener
        service["listener_yaml"] = yaml.safe_dump(listener, allow_unicode=True, sort_keys=False).strip()
    return listener


def local_listener_names(state_obj):
    names = set()
    for service in (state_obj or {}).get("local_services") or []:
        listener = service.get("listener") if isinstance(service, dict) else None
        name = listener.get("name") if isinstance(listener, dict) else None
        if not name:
            text = service.get("listener_yaml") if isinstance(service, dict) else ""
            if text and str(text).strip():
                try:
                    nodes = parse_yaml_snippet(text)
                    if len(nodes) == 1 and isinstance(nodes[0], dict):
                        name = nodes[0].get("name")
                except Exception:
                    pass
        if name:
            names.add(str(name))
    return names


def chain_entry_listener_names(state_obj):
    chain = (state_obj or {}).get("chain") or {}
    entry = chain.get("entry") or {}
    name = entry.get("name") if isinstance(entry, dict) else None
    return {str(name)} if name else set()


def chain_proxy_names(state_obj):
    chain = (state_obj or {}).get("chain") or {}
    nodes = chain.get("nodes") or []
    names = set()
    for node in nodes:
        if isinstance(node, dict) and node.get("name"):
            names.add(str(node.get("name")))
    return names


def current_managed_names(state):
    managed = (state or {}).get("managed") or {}
    persisted_state = load_yaml(STATE_PATH, default_state())
    persisted_managed = (persisted_state or {}).get("managed") or {}

    listener_names = (
        set(managed.get("listener_names") or [])
        | set(persisted_managed.get("listener_names") or [])
        | local_listener_names(state)
        | local_listener_names(persisted_state)
        | chain_entry_listener_names(state)
        | chain_entry_listener_names(persisted_state)
    )
    proxy_names = (
        set(managed.get("proxy_names") or [])
        | set(persisted_managed.get("proxy_names") or [])
        | chain_proxy_names(state)
        | chain_proxy_names(persisted_state)
    )
    group_names = set(managed.get("proxy_group_names") or []) | set(persisted_managed.get("proxy_group_names") or [])

    return {
        "listeners": listener_names,
        "proxies": proxy_names,
        "groups": group_names,
    }


def without_managed(items, names):
    if not isinstance(items, list):
        return []
    return [item for item in items if not isinstance(item, dict) or item.get("name") not in names]


def names_from_items(items):
    if not isinstance(items, list):
        return set()
    return {str(item.get("name")) for item in items if isinstance(item, dict) and item.get("name")}


def ports_from_items(items):
    ports = set()
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and item.get("port") is not None:
                try:
                    ports.add(int(item["port"]))
                except (TypeError, ValueError):
                    pass
    return ports


def next_available_port(port, used_ports=None):
    used_ports = set(used_ports or set())
    while int(port) in used_ports:
        port = int(port) + 1
    return int(port)


def build_managed_objects(state, used_listener_names=None, split_route=True):
    listeners, proxies, groups = [], [], []
    used_listener_names = set(used_listener_names or set()) | set(current_managed_names(state).get("listeners") or [])
    for service in state.get("local_services") or []:
        if service.get("enabled"):
            listener = parse_listener_yaml(service, used_listener_names)
            if listener.get("name"):
                used_listener_names.add(str(listener["name"]))
            listeners.append(listener)
    chain = state.get("chain") or {}
    if chain.get("enabled") and chain.get("entry") and chain.get("nodes"):
        entry = copy.deepcopy(chain["entry"])
        nodes = copy.deepcopy(chain["nodes"])

        # 重新解析获取分级信息
        node_texts = [chain.get("entry_text")] + (chain.get("node_texts") or [])
        _, levels = normalize_chain_nodes(chain.get("node_texts") or [])

        # 为每级多节点创建 urltest 组
        previous_target = None  # 上一级的目标（单节点名或 urltest 组名）

        for level_index, level_nodes in enumerate(levels):
            if len(level_nodes) == 1:
                # 单节点，直接串联
                node = level_nodes[0]
                if previous_target:
                    node["dialer-proxy"] = previous_target
                previous_target = node["name"]
                proxies.append(node)
            else:
                # 多节点，创建 urltest 组
                group_name = f"chain-level{level_index+2}-urltest"

                # 所有同级节点的 dialer-proxy 指向上一级
                for node in level_nodes:
                    if previous_target:
                        node["dialer-proxy"] = previous_target
                    proxies.append(node)

                # 创建 urltest 组
                urltest_group = {
                    "name": group_name,
                    "type": "url-test",
                    "proxies": [node["name"] for node in level_nodes],
                    "url": "https://www.gstatic.com/generate_204",
                    "interval": 300,
                    "tolerance": 50,
                }
                groups.append(urltest_group)
                previous_target = group_name

        # 入口节点的 proxy 指向最后一级
        if split_route:
            entry.pop("proxy", None)
        else:
            entry["proxy"] = previous_target

        listeners.append(entry)
    return listeners, proxies, groups


def detect_port_conflicts(listeners):
    seen = {}
    conflicts = []
    for item in listeners:
        if not isinstance(item, dict) or "port" not in item:
            continue
        listen = item.get("listen") or "0.0.0.0"
        key = int(item["port"])
        previous = seen.get(key)
        if previous:
            conflicts.append(f"端口 {key} 同时被 {previous} 和 {item.get('name')} 使用")
        else:
            seen[key] = item.get("name") or listen
    return conflicts


def detect_name_conflicts(config):
    conflicts = []
    for section in ("listeners", "proxies", "proxy-groups"):
        seen = set()
        for item in config.get(section) or []:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            if name in seen:
                conflicts.append(f"{section} 中名称重复：{name}")
            seen.add(name)
    return conflicts


def normalize_performance_settings(settings=None):
    settings = settings or {}
    log_level = str(settings.get("log_level") or "warning")
    if log_level not in {"error", "warning", "info", "debug"}:
        log_level = "warning"
    try:
        timeout = int(settings.get("connection_timeout") or 5)
    except (TypeError, ValueError):
        timeout = 5
    if timeout not in {3, 5, 10}:
        timeout = 5
    return {
        "keep_alive": settings.get("keep_alive") is not False,
        "tcp_concurrent": settings.get("tcp_concurrent") is not False,
        "unified_delay": settings.get("unified_delay") is not False,
        "fake_ip": False,
        "split_route": settings.get("split_route") is not False,
        "ipv6": settings.get("ipv6") is True,
        "connection_timeout": timeout,
        "log_level": log_level,
        "tproxy": settings.get("tproxy") is True,
    }


def detect_performance_settings(config=None):
    config = config or load_yaml(CONFIG_PATH, {}) or {}
    dns = config.get("dns") or {}
    return normalize_performance_settings({
        "keep_alive": bool(config.get("keep-alive-interval")),
        "tcp_concurrent": config.get("tcp-concurrent") is True,
        "unified_delay": config.get("unified-delay") is True,
        "fake_ip": False,
        "split_route": config.get("x-split-route") is not False,
        "ipv6": config.get("ipv6") is True or dns.get("ipv6") is True,
        "connection_timeout": config.get("connection-timeout", 5),
        "log_level": config.get("log-level", "warning"),
        "tproxy": config.get("redir-port") == 7892 and config.get("routing-mark") == 255,
    })


PROXY_GROUP_NAME = "节点选择"


RESERVED_IP_RULES = [
    "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
    "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
    "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve",
    "IP-CIDR,224.0.0.0/4,DIRECT,no-resolve",
    "IP-CIDR,240.0.0.0/4,DIRECT,no-resolve",
    "IP-CIDR,198.18.0.1/16,REJECT,no-resolve",
]


def split_rule_providers():
    base = "https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@meta/geo"
    return {
        "cn_domain": {"type": "http", "behavior": "domain", "format": "mrs", "url": f"{base}/geosite/cn.mrs",      "path": "./ruleset/cn_domain.mrs", "interval": 86400},
        "cn_ip":     {"type": "http", "behavior": "ipcidr", "format": "mrs", "url": f"{base}/geoip/cn.mrs",        "path": "./ruleset/cn_ip.mrs",     "interval": 604800},
        "private":   {"type": "http", "behavior": "domain", "format": "mrs", "url": f"{base}/geosite/private.mrs", "path": "./ruleset/private.mrs",   "interval": 86400},
    }


def split_rules(match_target):
    """大陆白名单: 私网/CN 直连, 其余走 match_target"""
    return RESERVED_IP_RULES + [
        "RULE-SET,private,DIRECT",
        "RULE-SET,cn_domain,DIRECT",
        "RULE-SET,cn_ip,DIRECT,no-resolve",
        f"MATCH,{match_target}",
    ]


def global_rules(match_target):
    """全局代理: 仅私网直连, 其余全部走 match_target"""
    return RESERVED_IP_RULES + [f"MATCH,{match_target}"]


def apply_split_rules(config, proxy_names, match_target, split_route=True):
    config["geodata-mode"] = False
    config.pop("geodata-loader", None)
    config.pop("geo-auto-update", None)
    config.pop("geoip-format", None)
    if split_route:
        config["rule-providers"] = split_rule_providers()
        config["rules"] = split_rules(match_target)
    else:
        config.pop("rule-providers", None)
        config["rules"] = global_rules(match_target)

    # 收集所有代理节点 (排除链式节点，链式节点通过 match_target 引用)
    proxies = [name for name in proxy_names if name]

    # 如果有多个独立代理节点 (≥2)，创建自动切换组
    auto_group_name = "自动选择"
    groups = [g for g in config.get("proxy-groups") or [] if not (isinstance(g, dict) and g.get("name") in (PROXY_GROUP_NAME, auto_group_name))]

    if len(proxies) >= 2:
        # urltest: 每 300s 测速，选延迟最低节点
        groups.append({
            "name": auto_group_name,
            "type": "url-test",
            "proxies": proxies,
            "url": "https://www.gstatic.com/generate_204",
            "interval": 300,
            "tolerance": 50,
        })
        # 节点选择: 自动组优先，可手动切换
        select_proxies = [auto_group_name] + proxies
    else:
        select_proxies = proxies

    if "DIRECT" not in select_proxies:
        select_proxies.append("DIRECT")

    groups.append({"name": PROXY_GROUP_NAME, "type": "select", "proxies": select_proxies})
    config["proxy-groups"] = groups
    return PROXY_GROUP_NAME


def apply_performance_to_config(config, settings):
    settings = normalize_performance_settings(settings)
    config["log-level"] = settings["log_level"]
    config["ipv6"] = settings["ipv6"]
    config["tcp-concurrent"] = settings["tcp_concurrent"]
    config["unified-delay"] = settings["unified_delay"]
    config["connection-timeout"] = settings["connection_timeout"]
    config["external-controller"] = MIHOMO_CONTROLLER
    config["x-split-route"] = settings["split_route"]
    if settings["keep_alive"]:
        config["keep-alive-interval"] = 30
        config["keep-alive-idle"] = 600
    else:
        config.pop("keep-alive-interval", None)
        config.pop("keep-alive-idle", None)
    dns = config.setdefault("dns", {})
    dns["enable"] = True
    dns["ipv6"] = settings["ipv6"]
    dns["enhanced-mode"] = "redir-host"
    dns.pop("fake-ip-range", None)
    dns.pop("fake-ip-filter", None)
    profile = config.get("profile")
    if isinstance(profile, dict):
        profile.pop("store-fake-ip", None)
        if not profile:
            config.pop("profile", None)
    dns["respect-rules"] = True
    # bootstrap DNS: 解析 DoH 域名用，必须用纯 IP 避免循环
    dns["default-nameserver"] = ["223.5.5.5", "180.76.76.76", "119.29.29.29"]
    # 代理节点域名解析: 用国内 DNS，防代理服务器域名被墙/污染
    dns["proxy-server-nameserver"] = ["223.5.5.5", "180.76.76.76", "119.29.29.29"]
    # 主 DNS: 国外 DoH 走代理隧道查询
    dns["nameserver"] = ["https://cloudflare-dns.com/dns-query", "https://dns.google/dns-query"]
    if settings["split_route"]:
        # 白名单: CN 域名走国内 DNS 直连
        dns["nameserver-policy"] = {"rule-set:cn_domain": ["223.5.5.5", "180.76.76.76", "119.29.29.29"]}
    else:
        # 全局代理: 无 cn_domain provider, 移除 nameserver-policy
        dns.pop("nameserver-policy", None)
    dns.pop("fallback", None)
    dns.pop("fallback-filter", None)
    dns.pop("direct-nameserver", None)
    dns.pop("prefer-h3", None)
    if settings["tproxy"]:
        config["redir-port"] = 7892
        config["routing-mark"] = 255
        dns["listen"] = "0.0.0.0:1053"
    else:
        config.pop("redir-port", None)
        config.pop("routing-mark", None)
        dns.pop("listen", None)
    return settings


def render_config(existing, state):
    config = copy.deepcopy(existing or {})
    settings = state.get("performance") or detect_performance_settings(config)
    settings = apply_performance_to_config(config, settings)
    old = current_managed_names(state)
    config["listeners"] = without_managed(config.get("listeners"), old["listeners"])
    config["proxies"] = without_managed(config.get("proxies"), old["proxies"])
    config["proxy-groups"] = without_managed(config.get("proxy-groups"), old["groups"])
    used_listener_names = names_from_items(config.get("listeners"))
    listeners, proxies, groups = build_managed_objects(state, used_listener_names, settings["split_route"])
    config["listeners"].extend(listeners)
    if proxies:
        config["proxies"].extend(proxies)
    elif not config["proxies"]:
        config.pop("proxies", None)
    proxy_names = names_from_items(config.get("proxies"))
    chain = state.get("chain") or {}
    match_target = chain["exit_proxy"] if (chain.get("enabled") and chain.get("exit_proxy")) else PROXY_GROUP_NAME
    group_name = apply_split_rules(config, proxy_names, match_target, settings["split_route"])
    groups = [g for g in groups if g.get("name") != group_name]
    if groups:
        config["proxy-groups"].extend(groups)
    errors = detect_name_conflicts(config) + detect_port_conflicts(config.get("listeners") or [])
    if errors:
        raise ValueError("\n".join(errors))
    next_state = copy.deepcopy(state)
    next_state["managed"] = {
        "listener_names": [item["name"] for item in listeners if item.get("name")],
        "proxy_names": [item["name"] for item in proxies if item.get("name")],
        "proxy_group_names": [group_name] + [item["name"] for item in groups if item.get("name")],
    }
    return config, next_state


def validate_config_file(path):
    return command_result([str(MIMO_BINARY), "-d", str(APP_DIR), "-t", "-f", str(path)], 180)


def reload_mihomo_api():
    host, port = MIHOMO_CONTROLLER.rsplit(":", 1)
    started = time.time()
    try:
        conn = HTTPConnection(host, int(port), timeout=8)
        conn.request("PUT", "/configs?force=true", body=json.dumps({"path": str(CONFIG_PATH)}), headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        conn.close()
        return {"ok": 200 <= response.status < 300, "method": "api", "status": response.status, "elapsed_ms": int((time.time() - started) * 1000), "output": body[-2000:]}
    except Exception as e:
        return {"ok": False, "method": "api", "elapsed_ms": int((time.time() - started) * 1000), "output": str(e)}


def patch_mihomo_config(patch_data):
    """PATCH partial config update — no full reload, no DNS cache flush"""
    host, port = MIHOMO_CONTROLLER.rsplit(":", 1)
    started = time.time()
    try:
        conn = HTTPConnection(host, int(port), timeout=8)
        conn.request("PATCH", "/configs", body=json.dumps(patch_data), headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        conn.close()
        return {"ok": 200 <= response.status < 300, "method": "patch", "status": response.status, "elapsed_ms": int((time.time() - started) * 1000), "output": body[-500:]}
    except Exception as e:
        return {"ok": False, "method": "patch", "elapsed_ms": int((time.time() - started) * 1000), "output": str(e)}


def reload_mihomo_signal():
    result = command_result(["systemctl", "reload", MIMO_SERVICE_NAME], 180)
    if not result["ok"]:
        restart = command_result(["systemctl", "restart", MIMO_SERVICE_NAME], 180)
        restart["reload_output"] = result.get("output", "")
        result = restart
    result["method"] = "systemd"
    return result


def recreate_mihomo():
    api = reload_mihomo_api()
    if api["ok"]:
        return api
    signal = reload_mihomo_signal()
    signal["api"] = api
    return signal


def google_connectivity_command(state=None):
    config = load_yaml(CONFIG_PATH, {})
    chain = (state or {}).get("chain") or {}
    entry = chain.get("entry") or {}
    entry_type = str(entry.get("type", "")).lower()
    entry_port = entry.get("port")
    target = "https://www.google.com/generate_204"
    cmd = ["curl", "-I", "-L", target]
    mode = "direct"
    if chain.get("enabled") and entry_port and entry_type in ("http", "socks"):
        users = entry.get("users") or []
        proxy_args = []
        if users and isinstance(users[0], dict) and users[0].get("username"):
            proxy_args = ["-U", f"{users[0].get('username')}:{users[0].get('password', '')}"]
        scheme = "socks5h" if entry_type == "socks" else "http"
        cmd[1:1] = ["-x", f"{scheme}://127.0.0.1:{entry_port}"] + proxy_args
        mode = f"chain-entry-{entry_type}-{entry_port}"
    return target, mode, cmd


def test_google_connectivity(state=None):
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target, mode, cmd = google_connectivity_command(state)
    cmd = cmd[:]
    cmd[1:1] = ["--max-time", "5", "--connect-timeout", "3"]
    last_result = None
    for attempt in range(1, 3):
        try:
            start = time.monotonic()
            result = command_result(cmd, 3)
            result["elapsed_ms"] = int((time.monotonic() - start) * 1000)
            result["attempt"] = attempt
            last_result = result
            if result["ok"]:
                return {"ok": True, "checked_at": checked_at, "target": target, "mode": mode, "attempt": attempt, "returncode": result["returncode"], "elapsed_ms": result["elapsed_ms"], "output": result["output"][-2000:]}
        except Exception as e:
            last_result = {"ok": False, "attempt": attempt, "returncode": -1, "elapsed_ms": None, "output": str(e)}
        if attempt < 2:
            time.sleep(0.2)
    return {"ok": False, "checked_at": checked_at, "target": target, "mode": mode, "attempt": last_result.get("attempt"), "returncode": last_result.get("returncode"), "elapsed_ms": last_result.get("elapsed_ms"), "output": last_result.get("output", "")[-2000:]}


def test_google_connectivity_quick(state=None):
    checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target, mode, cmd = google_connectivity_command(state)
    cmd = cmd[:]
    cmd[1:1] = ["--max-time", "0.7", "--connect-timeout", "0.7"]
    last_result = None
    for attempt in range(1, 3):
        try:
            start = time.monotonic()
            result = command_result(cmd, 2)
            result["elapsed_ms"] = int((time.monotonic() - start) * 1000)
            result["attempt"] = attempt
            last_result = result
            if result["ok"]:
                return {"ok": True, "checked_at": checked_at, "target": target, "mode": mode, "attempt": attempt, "returncode": result["returncode"], "elapsed_ms": result["elapsed_ms"], "output": result["output"][-2000:]}
        except Exception as e:
            last_result = {"ok": False, "attempt": attempt, "returncode": -1, "elapsed_ms": None, "output": str(e)}
        if attempt < 2:
            time.sleep(0.1)
    return {"ok": False, "checked_at": checked_at, "target": target, "mode": mode, "attempt": last_result.get("attempt"), "returncode": last_result.get("returncode"), "elapsed_ms": last_result.get("elapsed_ms"), "output": last_result.get("output", "")[-2000:]}


def write_candidate(config):
    fd, path = tempfile.mkstemp(prefix="config.yaml.", suffix=".pending", dir=str(APP_DIR))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
    return Path(path)


def validate_state(state):
    existing = load_yaml(CONFIG_PATH, {})
    candidate, next_state = render_config(existing, state)
    pending = write_candidate(candidate)
    try:
        result = validate_config_file(pending)
        return result, pending, next_state
    except Exception:
        pending.unlink(missing_ok=True)
        raise


def _tproxy_bypass_ports(config):
    ports = set()
    for lst in config.get("listeners") or []:
        p = lst.get("port")
        if p is not None:
            ports.add(int(p))
    dns = config.get("dns") or {}
    dns_listen = dns.get("listen", "")
    dns_port = str(dns_listen).rsplit(":", 1)[-1] if dns_listen else ""
    if dns_port and dns_port.isdigit():
        ports.add(int(dns_port))
    controller = config.get("external-controller", "")
    ctrl_port = str(controller).rsplit(":", 1)[-1] if controller else ""
    if ctrl_port and ctrl_port.isdigit():
        ports.add(int(ctrl_port))
    redir = config.get("redir-port")
    if redir is not None:
        ports.add(int(redir))
    ports.add(PORT)          # console itself
    try:
        ssh_out = subprocess.run(["ss", "-lntp"], capture_output=True, text=True, timeout=5).stdout
        for line in ssh_out.splitlines():
            if "sshd" in line:
                m = re.search(r":(\d{2,5})\s", line)
                if m:
                    ports.add(int(m.group(1)))
    except Exception:
        ports.add(22)
    return sorted(ports)


def _apply_tproxy_bypass(config):
    ports = _tproxy_bypass_ports(config)
    port_list = ",".join(str(p) for p in ports)
    IPT = "iptables-legacy"
    DNS_PORT = str(config.get("dns", {}).get("listen", "1053")).rsplit(":", 1)[-1]
    REDIR_PORT = str(config.get("redir-port", "7892"))
    ROUTING_MARK = str(config.get("routing-mark", "255"))

    # ---- nat 表: cleanup ----
    subprocess.run([IPT, "-t", "nat", "-F", "MIMO_REDIR"], capture_output=True, timeout=5)
    subprocess.run([IPT, "-t", "nat", "-X", "MIMO_REDIR"], capture_output=True, timeout=5)
    for chain in ["OUTPUT", "PREROUTING"]:
        for proto in [["-p", "tcp"], ["-p", "udp", "--dport", "53"]]:
            subprocess.run([IPT, "-t", "nat", "-D", chain] + proto + ["-j", "MIMO_REDIR"], capture_output=True, timeout=5)

    # ---- nat: MIMO_REDIR 链 (TCP REDIRECT + DNS 劫持) ----
    subprocess.run([IPT, "-t", "nat", "-N", "MIMO_REDIR"], capture_output=True, timeout=5)
    nat_rules = [
        # 防回环: Mihomo 自身出站带 mark → 跳过
        [IPT, "-t", "nat", "-A", "MIMO_REDIR", "-m", "mark", "--mark", ROUTING_MARK, "-j", "RETURN"],
        # 端口绕过 (SSH/Console/Listeners/DNS/Controller)
        [IPT, "-t", "nat", "-A", "MIMO_REDIR", "-p", "tcp", "-m", "multiport", "--dports", port_list, "-j", "RETURN"],
        [IPT, "-t", "nat", "-A", "MIMO_REDIR", "-p", "udp", "-m", "multiport", "--dports", port_list, "-j", "RETURN"],
        # DNS 劫持 → Mihomo DNS (必须在私有 IP RETURN 之前: 内网 DNS 如 WSL 172.30.x 的 :53 查询否则会被绕过 → DNS 污染)
        [IPT, "-t", "nat", "-A", "MIMO_REDIR", "-p", "tcp", "--dport", "53", "-j", "REDIRECT", "--to-ports", DNS_PORT],
        [IPT, "-t", "nat", "-A", "MIMO_REDIR", "-p", "udp", "--dport", "53", "-j", "REDIRECT", "--to-ports", DNS_PORT],
    ]
    # 保留/私有地址直连
    for ip in ["127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
               "169.254.0.0/16", "100.64.0.0/10", "224.0.0.0/4", "240.0.0.0/4"]:
        nat_rules.append([IPT, "-t", "nat", "-A", "MIMO_REDIR", "-d", ip, "-j", "RETURN"])
    # 云厂商内网绕过: 元数据/内网 DNS/VPC 服务
    # 腾讯云: 169.254.0.23(metadata) 已含在169.254.0.0/16
    # 阿里云: 100.100.100.200(metadata) 已含在100.64.0.0/10
    # 额外明确加 /32 确保不被漏掉
    cloud_ips = [
        "169.254.0.23",        # 腾讯云 metadata
        "100.100.100.200",     # 阿里云 metadata
    ]
    # 本机公网 IP 也绕过 (防自连)
    try:
        pub_ip = subprocess.run(["curl", "-fsSL", "--max-time", "3", "ifconfig.me"], capture_output=True, text=True, timeout=5).stdout.strip()
        if pub_ip and re.match(r"^\d+\.\d+\.\d+\.\d+$", pub_ip):
            cloud_ips.append(pub_ip)
    except Exception:
        pass
    for ip in cloud_ips:
        nat_rules.append([IPT, "-t", "nat", "-A", "MIMO_REDIR", "-d", ip, "-j", "RETURN"])
    # DNS 劫持已前置 (私有 IP RETURN 之前)。此处仅 TCP 全劫持 → redir 端口
    nat_rules += [
        # TCP 全部劫持 → redir 端口
        [IPT, "-t", "nat", "-A", "MIMO_REDIR", "-p", "tcp", "-j", "REDIRECT", "--to-ports", REDIR_PORT],
    ]
    for cmd in nat_rules:
        subprocess.run(cmd, capture_output=True, timeout=5)
    # 挂载到 OUTPUT (本机) + PREROUTING (其他设备)
    for chain in ["OUTPUT", "PREROUTING"]:
        for proto in [["-p", "tcp"], ["-p", "udp", "--dport", "53"]]:
            check = subprocess.run([IPT, "-t", "nat", "-C", chain] + proto + ["-j", "MIMO_REDIR"], capture_output=True, timeout=5)
            if check.returncode != 0:
                subprocess.run([IPT, "-t", "nat", "-I", chain] + proto + ["-j", "MIMO_REDIR"], capture_output=True, timeout=5)

    # ---- filter/INPUT: QUIC 阻断 ----
    # QUIC (UDP 443) 不被 REDIRECT 劫持 (REDIRECT 仅 TCP)
    # 阻断 UDP 443 强制浏览器回退 HTTPS/TCP → 进入透明代理
    subprocess.run([IPT, "-D", "INPUT", "-p", "udp", "--dport", "443", "-j", "REJECT"], capture_output=True, timeout=5)
    subprocess.run([IPT, "-I", "INPUT", "-p", "udp", "--dport", "443", "-j", "REJECT", "--reject-with", "icmp-port-unreachable"], capture_output=True, timeout=5)

    return port_list


def apply_performance_settings(settings):
    with LOCK:
        config = load_yaml(CONFIG_PATH, {})
        prev_tproxy = bool(config.get("redir-port"))
        prev_split = config.get("x-split-route") is not False
        normalized = apply_performance_to_config(config, settings)
        state = load_yaml(STATE_PATH, default_state())
        tproxy_changed = bool(normalized.get("tproxy")) != prev_tproxy
        split_changed = bool(normalized.get("split_route")) != prev_split

        # 分流开关变化 → 重建路由规则 (tproxy 已与路由解耦, 不再触发重建)
        if split_changed:
            proxy_names = names_from_items(config.get("proxies"))
            chain = state.get("chain") or {}
            match_target = chain["exit_proxy"] if (chain.get("enabled") and chain.get("exit_proxy")) else PROXY_GROUP_NAME
            apply_split_rules(config, proxy_names, match_target, normalized["split_route"])

        # Validate and save
        pending = write_candidate(config)
        result = validate_config_file(pending)
        if not result["ok"]:
            pending.unlink(missing_ok=True)
            return {"ok": False, "stage": "validate", "validation": result, "performance": normalized}
        save_config_in_place(CONFIG_PATH, load_yaml(pending, {})); pending.unlink(missing_ok=True)
        state["performance"] = normalized
        save_yaml_atomic(STATE_PATH, state)

        # Reload: 全量 reload 仅在 tproxy 或 分流 切换时; 其余轻量 PATCH
        IPT = "iptables-legacy"
        tproxy_svc = "mimo-tproxy.service"
        if tproxy_changed or split_changed:
            reload = recreate_mihomo()
            if tproxy_changed and normalized.get("tproxy"):
                subprocess.run(["systemctl", "enable", "--now", tproxy_svc], capture_output=True, timeout=15)
                _apply_tproxy_bypass(config)
            elif tproxy_changed:
                subprocess.run(["systemctl", "disable", "--now", tproxy_svc], capture_output=True, timeout=15)
                subprocess.run([IPT, "-D", "INPUT", "-p", "udp", "--dport", "443", "-j", "REJECT"], capture_output=True, timeout=5)
        else:
            # PATCH only changed sections: keeps DNS cache + connections alive
            patch = {}
            for key in ["log-level", "ipv6", "tcp-concurrent", "unified-delay", "connection-timeout",
                        "keep-alive-interval", "keep-alive-idle"]:
                if key in config:
                    patch[key] = config[key]
                elif key == "keep-alive-interval":
                    patch[key] = None  # signal removal
            patch["dns"] = config.get("dns", {})
            reload = patch_mihomo_config(patch)

        return {"ok": reload["ok"], "stage": "reload" if (tproxy_changed or split_changed) else "patch", "validation": result, "reload": reload, "container": container_status(), "performance": normalized}


def apply_state(state):
    with LOCK:
        result, pending, next_state = validate_state(state)
        if not result["ok"]:
            pending.unlink(missing_ok=True)
            return {"ok": False, "stage": "validate", "validation": result}
        save_config_in_place(CONFIG_PATH, load_yaml(pending, {})); pending.unlink(missing_ok=True)
        save_yaml_atomic(STATE_PATH, next_state)
        reload = recreate_mihomo()
        if reload["ok"] and (next_state.get("chain") or {}).get("enabled"):
            connectivity = test_google_connectivity(next_state)
        elif reload["ok"]:
            connectivity = None
        else:
            connectivity = {"ok": False, "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "error": "热加载失败，未测试 google.com"}
        next_state["connectivity"] = connectivity
        save_yaml_atomic(STATE_PATH, next_state)
        return {"ok": reload["ok"], "stage": "connectivity" if reload["ok"] and connectivity else "reload", "validation": result, "reload": reload, "connectivity": connectivity, "container": container_status(), "state": next_state, "performance": next_state.get("performance") or detect_performance_settings()}


def make_auth_file():
    if AUTH_PATH.exists():
        return
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", b"admin12", salt, 200000)
    data = {"username": "admin12", "algorithm": "pbkdf2_sha256", "iterations": 200000, "salt": base64.b64encode(salt).decode(), "hash": base64.b64encode(digest).decode()}
    save_yaml_atomic(AUTH_PATH, data)
    os.chmod(AUTH_PATH, 0o600)


def check_auth(header):
    if not header or not header.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(header.split(" ", 1)[1]).decode()
        username, password = raw.split(":", 1)
        auth = load_yaml(AUTH_PATH, {})
        if not hmac.compare_digest(username, str(auth.get("username", ""))):
            return False
        salt = base64.b64decode(auth["salt"])
        expected = base64.b64decode(auth["hash"])
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(auth.get("iterations", 200000)))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def default_state():
    return {"version": 1, "local_services": [], "chain": {"enabled": False, "entry_text": "", "node_texts": [""], "entry": None, "nodes": [], "exit_proxy": ""}, "managed": {"listener_names": [], "proxy_names": [], "proxy_group_names": []}, "connectivity": None, "performance": normalize_performance_settings()}


def ensure_initialized_state():
    if not INIT_MARKER_PATH.exists():
        save_yaml_atomic(STATE_PATH, default_state())
        INIT_MARKER_PATH.write_text(datetime.now().isoformat(), encoding="utf-8")
        return
    if not STATE_PATH.exists():
        save_yaml_atomic(STATE_PATH, default_state())


def json_response(handler, status, data):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Expires", "0")
    handler._set_login_cookie()
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


TOKEN_PATH = CONSOLE_DIR / "tokens.yaml"
TOKEN_MAX_AGE = 365 * 86400  # 1 year

def _load_tokens():
    return load_yaml(TOKEN_PATH, {})


def _save_tokens(data):
    save_yaml_atomic(TOKEN_PATH, data)
    os.chmod(TOKEN_PATH, 0o600)


def check_token(token):
    if not token:
        return False
    tokens = _load_tokens()
    entry = tokens.get(token)
    if not entry:
        return False
    if time.time() > entry.get("expires", 0):
        tokens.pop(token, None)
        _save_tokens(tokens)
        return False
    return True


def issue_token():
    """one token per process lifespan — reused until expiry"""
    tokens = _load_tokens()
    now = time.time()
    # reuse existing non-expired token for admin12
    for tok, entry in list(tokens.items()):
        if entry.get("user") == "admin12" and now < entry.get("expires", 0):
            return tok
    # prune expired
    tokens = {k: v for k, v in tokens.items() if now < v.get("expires", 0)}
    # new token
    token = secrets.token_urlsafe(32)
    tokens[token] = {"user": "admin12", "created": now, "expires": now + TOKEN_MAX_AGE}
    _save_tokens(tokens)
    return token


class Handler(BaseHTTPRequestHandler):
    server_version = "mimo-console/1.0"

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="mimo console"')
        self.end_headers()

    def require_auth(self):
        # 1) check cookie token (persistent login)
        cookie = self.headers.get("Cookie", "")
        token_match = re.search(r"mimo_token=([^;]+)", cookie)
        if token_match and check_token(token_match.group(1)):
            return True
        # 2) check Basic Auth
        if check_auth(self.headers.get("Authorization")):
            # issue persistent token via Set-Cookie header
            token = issue_token()
            # store for response headers
            self._login_token = token
            return True
        # 认证失败，记录日志供 fail2ban 监控
        client_ip = self.client_address[0]
        print(f"[AUTH_FAIL] {client_ip} - Authorization failed", flush=True)
        self.do_AUTHHEAD()
        return False

    def _set_login_cookie(self):
        if hasattr(self, "_login_token"):
            self.send_header("Set-Cookie",
                f"mimo_token={self._login_token}; Max-Age={TOKEN_MAX_AGE}; Path=/; HttpOnly; SameSite=Lax")

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self):
        if not self.require_auth():
            return
        path = urlparse(self.path).path
        if path == "/":
            refresh_public_ip_cache_async()
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self._set_login_cookie()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/state":
            refresh_public_ip_cache_async()
            state = load_yaml(STATE_PATH, default_state())
            config = load_yaml(CONFIG_PATH, {})
            performance = state.get("performance") or detect_performance_settings(config)
            state["performance"] = performance
            with IP_CACHE_LOCK:
                cached_ip = IP_CACHE["ip"]
            json_response(self, 200, {"ok": True, "state": state, "container": container_status(), "connectivity": state.get("connectivity"), "performance": performance, "public_ip": cached_ip})
            return
        json_response(self, 404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if not self.require_auth():
            return
        path = urlparse(self.path).path
        try:
            data = self.read_json()
            if path == "/api/parse/local-services":
                current_state = load_yaml(STATE_PATH, default_state())
                current_config = load_yaml(CONFIG_PATH, {}) or {}
                used_names = set(data.get("existing_names") or []) | local_listener_names(current_state) | names_from_items(current_config.get("listeners"))
                used_ports = set(int(port) for port in (data.get("existing_ports") or []) if str(port).isdigit()) | ports_from_items(current_config.get("listeners")) | ports_from_items([service.get("listener") for service in (current_state.get("local_services") or []) if isinstance(service, dict)])
                services = []
                port_changes = []
                for node in parse_yaml_snippet(data.get("yaml", "")):
                    requested_port = int(node["port"]) if isinstance(node, dict) and node.get("port") is not None else None
                    listener = proxy_snippet_to_listener(node, used_names, used_ports)
                    if requested_port is not None and listener.get("port") is not None and int(listener["port"]) != requested_port:
                        port_changes.append({"name": listener.get("name"), "requested": requested_port, "assigned": int(listener["port"])})
                    card = listener_to_card(listener, used_names)
                    if card["listener"].get("name"):
                        used_names.add(str(card["listener"]["name"]))
                    if card["listener"].get("port") is not None:
                        used_ports.add(int(card["listener"]["port"]))
                    services.append(card)
                json_response(self, 200, {"ok": True, "services": services, "port_changes": port_changes})
                return
            if path == "/api/parse/chain":
                entry_text = data.get("entry_yaml", "")
                node_texts = data.get("node_yamls") or []
                entry = normalize_entry_listener(entry_text)
                nodes, levels = normalize_chain_nodes(node_texts)
                # 返回最后一级的代表节点名或 urltest 组名
                last_level = levels[-1] if levels else []
                exit_proxy = f"chain-level{len(levels)+1}-urltest" if len(last_level) > 1 else (last_level[0]["name"] if last_level else nodes[-1]["name"])
                json_response(self, 200, {"ok": True, "entry": entry, "nodes": nodes, "exit_proxy": exit_proxy})
                return
            if path == "/api/local-node":
                listener = parse_listener_yaml(data.get("service") or {})
                ip, cached = public_ip_cached()
                text = listener_to_client_node(listener, ip)
                json_response(self, 200, {"ok": True, "public_ip": ip, "ip_cached": cached, "yaml": text})
                return
            if path == "/api/local-node-url":
                listener = parse_listener_yaml(data.get("service") or {})
                ip, cached = public_ip_cached()
                url = listener_to_client_url(listener, ip)
                json_response(self, 200, {"ok": True, "public_ip": ip, "ip_cached": cached, "url": url})
                return
            if path == "/api/save-state":
                state = data.get("state") or default_state()
                save_yaml_atomic(STATE_PATH, state)
                json_response(self, 200, {"ok": True, "state": state})
                return
            if path == "/api/performance":
                result = apply_performance_settings(data.get("settings") or {})
                json_response(self, 200 if result.get("ok") else 400, result)
                return
            if path == "/api/connectivity-test":
                state = load_yaml(STATE_PATH, default_state())
                connectivity = test_google_connectivity_quick(state)
                state["connectivity"] = connectivity
                save_yaml_atomic(STATE_PATH, state)
                json_response(self, 200, {"ok": connectivity.get("ok", False), "connectivity": connectivity})
                return
            if path == "/api/validate":
                with LOCK:
                    result, pending, _ = validate_state(data.get("state") or default_state())
                    pending.unlink(missing_ok=True)
                json_response(self, 200 if result["ok"] else 400, {"ok": result["ok"], "validation": result})
                return
            if path == "/api/apply":
                result = apply_state(data.get("state") or default_state())
                json_response(self, 200 if result.get("ok") else 400, result)
                return
            json_response(self, 404, {"ok": False, "error": "not found"})
        except Exception as e:
            json_response(self, 400, {"ok": False, "error": str(e)})

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


def main():
    CONSOLE_DIR.mkdir(parents=True, exist_ok=True)
    make_auth_file()
    ensure_initialized_state()
    refresh_public_ip_cache_async(force=True)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"mimo console listening on {HOST}:{PORT}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
