# Mimo/Mihomo VPS 代理 — 交接文档

> **维护规则：每次改动配置/代码后，更新 git 提交并同步更新本文档。**

## 这是什么

基于 Mihomo (Clash.Meta) 内核的一键部署代理方案。部署后 VPS 具备：

- **多协议入站** — TUIC / Hysteria2 / AnyTLS / Shadowsocks / HTTP / SOCKS5
- **链式代理** — 入口 → 多级节点串联 → 互联网，支持同级备用自动切换
- **国内外分流** — 大陆 IP/域名直连，其余走代理
- **透明代理** — nftables 劫持本机 TCP+DNS，无需逐个程序配代理
- **Web 控制台** — 所有操作在浏览器完成，无需 SSH

## 目录结构

```
/root/projects/20260515-mimo443/
├── README.md          ← 本文档
└── mimo443/
    ├── start.sh                   安装/管理脚本（一切从这里开始）
    ├── config.yaml                Mihomo 运行配置
    ├── mimo-linux-amd64           x86_64 内核
    ├── mimo-linux-arm64-a53       ARM64 内核
    ├── console/
    │   ├── console.py             Web 控制台（端口 2000）
    │   ├── console-auth.yaml      控制台登录密码
    │   └── state.yaml             UI 状态
    └── ruleset/
        ├── server.crt / server.key  TLS 证书
        ├── cn_domain.mrs           中国域名规则
        ├── cn_ip.mrs               中国 IP 规则
        └── private.mrs             私有域名规则
```

## 部署

```bash
sudo bash /root/projects/20260515-mimo443/mimo443/start.sh
# 选 1) 安装并启动
```

依赖自动安装。部署后 2 个 systemd 服务默认 enable，透明代理需手动开启：

| 服务 | 端口 | 说明 |
|------|------|------|
| `mimo.service` | 7892, 1053, 19093 | 内核 |
| `mimo-console.service` | 2000 | Web 控制台 |
| `mimo-tproxy.service` | — | 透明代理 nftables（手动开启） |

透明代理默认关闭。开启：`systemctl enable --now mimo-tproxy.service`。关闭：`systemctl disable --now mimo-tproxy.service`。

**绕过端口**（不走代理，避免锁死）：SSH `22` 与 `60000-60050`、控制台 `2000`、控制器 `19093`、redir `7892`、DNS `1053`，以及 `config.yaml` 里所有入站 listener 端口（自动从配置提取）。本机公网 IP 也绕过。规则查看：`nft list table ip mimo_tproxy`。

## 控制台

浏览器打开 `http://VPS_IP:2000/`，用户名 `admin12`，密码为安装时生成的 UUID（存储在 `/root/projects/20260515-mimo443/mimo443/uuid`）。

### 功能面板

**搭建本地服务端** — 一键添加入站协议，生成客户端连接 URL。

**搭建链式代理** — 入口节点 → 多级出站串联。点「+ 备用」添加故障切换节点，同级多个节点自动 urltest 选优。

**功能选项** — 所有开关点即生效：

| 开关 | 作用 |
|------|------|
| 仅允许本机访问 | 入口绑定 127.0.0.1，外网不可直连 |
| VPS透明代理 | nftables 劫持本机所有 TCP+DNS |
| TCP并发 | 同目标多 IP 并发提速 |
| 国内外分流 | 开=大陆直连, 关=全局走代理 |
| 超时 | 3/5/10 秒 |
| 日志级别 | error/warning/info/debug |

### 操作流程

1. **搭建服务端** → 点协议按钮添加入站
2. **搭建链式代理** → 选入口类型 → 填节点 → 开开关 → 点应用
3. **切换功能** → 直接点选项，即时生效

日志区显示最近 5 条操作结果，最新在上，旧行渐淡。

## 管理命令

```bash
# 服务管理
systemctl start/stop/restart mimo.service mimo-console.service
systemctl enable --now mimo-tproxy.service    # 开透明代理
systemctl disable --now mimo-tproxy.service   # 关透明代理

# 查看状态
bash /root/projects/20260515-mimo443/mimo443/start.sh status

# 配置校验
/root/projects/20260515-mimo443/mimo443/mimo-linux-amd64 \
  -d /root/projects/20260515-mimo443/mimo443 \
  -t -f /root/projects/20260515-mimo443/mimo443/config.yaml

# 查看规则命中
curl -s http://127.0.0.1:19093/proxies
curl -s http://127.0.0.1:19093/rules
```

## 客户端使用代理

```bash
# 临时当前 shell
export http_proxy="http://用户名:密码@127.0.0.1:入口端口"
export https_proxy="$http_proxy"

# APT
echo 'Acquire::http::Proxy "http://用户名:密码@127.0.0.1:入口端口";' \
  > /etc/apt/apt.conf.d/99proxy

# Docker systemd
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/http-proxy.conf <<'EOF'
[Service]
Environment="HTTP_PROXY=http://用户名:密码@127.0.0.1:入口端口"
Environment="HTTPS_PROXY=http://用户名:密码@127.0.0.1:入口端口"
Environment="NO_PROXY=localhost,127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
EOF
systemctl daemon-reload && systemctl restart docker
```

## 国内外分流

规则来源：MetaCubeX geosite/geoip，每日自动更新。

```
大陆域名 → DIRECT（直连）
大陆 IP   → DIRECT（直连）
私有地址  → DIRECT（直连）
其余      → 节点选择（走代理）
```

## DNS

```
国内域名 → 223.5.5.5 / 180.76.76.76（直连）
国外域名 → cloudflare-dns.com / dns.google（DoH 走代理隧道）
```

## 安全

- 控制台监听 0.0.0.0:2000，暴露公网需注意
- 入口 HTTP 代理需要用户名密码认证
- 不要在任何地方泄露密码

## 故障排查

```bash
# 看服务状态
systemctl status mimo.service mimo-console.service

# 端口监听
ss -lntp | grep -E ':(2000|2001|7892|1053|19093)'

# 服务日志
journalctl -u mimo.service -u mimo-console.service --no-pager -n 50

# 重载/重启
systemctl restart mimo.service
```

## 卸载

```bash
bash /root/projects/20260515-mimo443/mimo443/start.sh
# 选 6) 删除全部
```

## 配置参考

Mihomo 完整配置项：https://wiki.metacubex.one/config/
