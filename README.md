# Mimo 分流 HTTP 代理服务器交接文档

本目录是一个可直接部署的 Mimo/Mihomo 二进制服务端包，用于在 VPS 上提供带认证的 HTTP 入口代理，并按规则实现国内直连、国外走节点。

目标效果：

```text
客户端 / VPS 工具 -> http://用户名:密码@服务器IP:2002
国内网站、国内 IP -> DIRECT
国外网站、代理规则命中域名 -> 节点选择
规则下载 -> 节点选择
控制台 -> http://服务器IP:2000/
```

不要把它理解成整机透明代理。默认只提供 HTTP 入口代理。需要某个程序走代理，就给该程序设置 `http_proxy` / `https_proxy`，或在程序自己的配置里填代理地址。

## 目录内容

```text
start.sh                 安装、启动、停止、重载、清理脚本
tproxy.sh                透明代理 iptables 规则管理脚本
config.yaml              运行配置，包含入口、节点、规则、DNS
console/console.py       Web 控制台，监听 2000
console/console-auth.yaml 控制台账号密码哈希
certs/                   本地服务端证书材料
Country.mmdb             GeoIP 数据
geoip.metadb             Meta GeoIP 数据
geosite.dat              GeoSite 数据
ruleset/                 rule-provider 缓存
mimo-linux-amd64         x86_64 Linux 内核
mimo-linux-arm64-a53     ARM64 / Cortex-A53 内核
mimo-linux-armv7-router  ARMv7 路由器内核
cache.db                 运行缓存
```

## 部署环境

推荐：

```text
OS: Debian/Ubuntu VPS
权限: root
init: systemd
CPU: x86_64 用 mimo-linux-amd64
端口: 2000 控制台，2002 HTTP 代理入口，19093 本机 controller，7892 redir，1053 DNS
```

依赖：

```text
curl
openssl
python3
python3-yaml
grep
sed
file
```

`start.sh` 会检查并尝试安装缺失依赖。

## 一键部署

```bash
sudo bash /root/Projects/20260515-mimo443/start.sh
```

菜单选择：

```text
1) 安装并重启/启动
```

部署后会写入并启用：

```text
/etc/systemd/system/mimo.service
/etc/systemd/system/mimo-console.service
/etc/systemd/system/mimo-tproxy.service
```

检查：

```bash
systemctl status --no-pager mimo.service mimo-console.service mimo-tproxy.service
ss -lntup | grep -E ':(2000|2002|19093|7892|1053)\b'
```

预期：

```text
mimo.service active
mimo-console.service active
0.0.0.0:2000 或 *:2000    控制台
*:2002                    HTTP 代理入口
127.0.0.1:19093           controller
```

## 管理菜单

```text
1) 安装并重启/启动
2) 热加载/重启控制台
3) 停止服务
4) 查看状态
5) 一键清理旧文件
6) 删除全部（危险）
7) 只重置控制台密码
0) 退出
```

常用命令：

```bash
bash /root/Projects/20260515-mimo443/start.sh
systemctl restart mimo.service mimo-console.service
systemctl reload mimo.service || systemctl restart mimo.service
systemctl stop mimo-console.service mimo.service
```

## 控制台

**默认监听 127.0.0.1:2000，仅本机访问。**

本机访问：

```bash
curl http://127.0.0.1:2000/
```

远程访问 (SSH 隧道)：

```bash
# 本地机器执行：
ssh -L 2000:127.0.0.1:2000 root@服务器IP

# 浏览器访问：
http://localhost:2000/
```

如需公网监听 (不推荐)，设置环境变量：

```bash
# /etc/systemd/system/mimo-console.service 添加：
Environment="CONSOLE_HOST=0.0.0.0"
```

控制台账号保存在：

```text
/root/Projects/20260515-mimo443/console/console-auth.yaml
```

只重置控制台密码：

```bash
bash /root/Projects/20260515-mimo443/start.sh
# 选择 7
```

控制台可做：

```text
新增本地服务端入口
新增链式代理入口
选择节点
切换国内外分流
切换 DNS
校验配置
应用配置并热加载
查看代理连接字符串
```

## HTTP 入口代理

当前入口在 `config.yaml` 的 `listeners` 中，典型结构：

```yaml
listeners:
- name: chain-entry-http-2002
  type: http
  port: 2002
  listen: 0.0.0.0
  users:
  - username: 用户名
    password: 密码
```

客户端使用：

```text
http://用户名:密码@服务器IP:2002
```

本机使用：

```text
http://用户名:密码@127.0.0.1:2002
```

注意：不要把真实用户名密码写进 README、脚本日志、issue、提交信息。

### 链式节点备用功能

支持为链式代理的第2级（及后续）节点配置备用节点，实现故障自动切换。

**使用方法：**

1. 访问 http://VPS_IP:2000/
2. 在"第2级节点"输入框填入主节点 YAML
3. 点击 **+ 备用** 按钮，自动追加备用节点模板
4. 修改备用节点的 IP、端口、密码

**效果：**
- 自动生成 `chain-level2-urltest` 故障切换组
- 每 300s 测速，选择延迟最低节点
- 主节点故障自动切换到备用节点
- 主节点恢复后自动切回

**手动配置示例：**

```yaml
# 第2级节点（双节点备用）
- name: level2-main
  type: ss
  server: 主节点IP
  port: 18000
  cipher: aes-128-gcm
  password: 密码
  udp: true
- name: level2-backup
  type: ss
  server: 备用IP
  port: 18001
  cipher: aes-128-gcm
  password: 密码
  udp: true
```

生成配置：
```yaml
proxy-groups:
- name: chain-level2-urltest
  type: url-test
  proxies: [level2-main, level2-backup]
  url: https://www.gstatic.com/generate_204
  interval: 300
```

## 多节点故障切换

当 `config.yaml` 中有多个 (≥2) 独立代理节点时，自动生成故障切换组：

```yaml
proxies:
- name: ss-main
  type: ss
  server: 主节点IP
  port: 18000
  cipher: aes-128-gcm
  password: 密码
  udp: true
- name: ss-backup-hk
  type: ss
  server: 备用节点IP
  port: 18001
  cipher: aes-128-gcm
  password: 密码
  udp: true

# 自动生成：
proxy-groups:
- name: 自动选择
  type: url-test           # 每 300s 测速，自动选延迟最低节点
  proxies:
  - ss-main
  - ss-backup-hk
  url: https://www.gstatic.com/generate_204
  interval: 300
  tolerance: 50
- name: 节点选择
  type: select             # 手动选择：自动组优先
  proxies:
  - 自动选择               # 默认选择自动组
  - ss-main                # 可手动切换到主节点
  - ss-backup-hk           # 可手动切换到备用节点
  - DIRECT
```

**行为:**
- 主节点正常: 自动选择主节点
- 主节点故障: 自动切换到延迟最低的备用节点
- 主节点恢复: 如果延迟更低，自动切回

**单节点模式:**
- 只有 1 个节点时，不生成自动选择组，直接用该节点

## 国内外分流逻辑

核心开关：

```yaml
x-split-route: true
```

开启后，控制台和配置生成逻辑会写入：

```yaml
rule-providers:
  direct:
    type: http
    behavior: domain
    url: https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/direct.txt
    path: ./ruleset/direct.yaml
    interval: 86400
    proxy: 节点选择
  proxy:
    type: http
    behavior: domain
    url: https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/proxy.txt
    path: ./ruleset/proxy.yaml
    interval: 86400
    proxy: 节点选择
  cncidr:
    type: http
    behavior: ipcidr
    url: https://cdn.jsdelivr.net/gh/Loyalsoldier/clash-rules@release/cncidr.txt
    path: ./ruleset/cncidr.yaml
    interval: 86400
    proxy: 节点选择
```

`proxy: 节点选择` 很重要。VPS 在中国或被墙网络中，规则下载必须走代理节点，否则 rule-provider 可能下载失败。

规则顺序：

```yaml
- IP-CIDR,10.0.0.0/8,DIRECT,no-resolve
- IP-CIDR,172.16.0.0/12,DIRECT,no-resolve
- IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
- IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
- IP-CIDR,169.254.0.0/16,DIRECT,no-resolve
- IP-CIDR,100.64.0.0/10,DIRECT,no-resolve
- IP-CIDR6,fc00::/7,DIRECT,no-resolve
- IP-CIDR6,fe80::/10,DIRECT,no-resolve
- RULE-SET,proxy,节点选择
- RULE-SET,direct,DIRECT
- RULE-SET,cncidr,DIRECT,no-resolve
- MATCH,节点选择
```

行为：

```text
局域网/保留地址 -> DIRECT
proxy 规则集 -> 节点选择
direct 规则集 -> DIRECT
cncidr 规则集 -> DIRECT
其他 -> 节点选择
```

如果关闭国内外分流：

```yaml
x-split-route: false
```

控制台会删除 `rule-providers`，规则变成：

```yaml
rules:
- MATCH,DIRECT
```

这时不会下载 direct/proxy/cncidr 规则。

## DNS 策略

采用多层 DNS 架构，防止污染和泄漏：

```yaml
dns:
  # Bootstrap DNS: 解析 DoH 域名用，纯 IP 避免循环依赖
  default-nameserver:
  - 223.5.5.5        # 阿里 DNS
  - 180.76.76.76     # 百度 DNS
  - 119.29.29.29     # 腾讯 DNSPod

  # 代理节点域名解析: 用国内 DNS，防代理服务器域名被墙
  proxy-server-nameserver:
  - 223.5.5.5
  - 180.76.76.76
  - 119.29.29.29

  # 主 DNS: 国外 DoH，走代理隧道查询 (防污染)
  nameserver:
  - https://cloudflare-dns.com/dns-query
  - https://dns.google/dns-query

  # 白名单模式: CN 域名走国内 DNS 直连
  nameserver-policy:
    rule-set:cn_domain:
    - 223.5.5.5
    - 180.76.76.76
    - 119.29.29.29

  # 透明代理模式启用 sniffer (强制域名嗅探)
  sniffer:
    enable: true
    force-domain: ["+"]
    skip-sni: ["www.baidu.com", "*.m.taobao.com", "*.alicdn.com"]
```

**DNS 查询流程:**
1. 国内域名 (cn_domain 规则集) → 国内 DNS 直连
2. 国外域名 → 国外 DoH 走代理隧道
3. 代理节点自身域名 → 国内 DNS (避免循环)
4. DoH 域名 (cloudflare-dns.com) → bootstrap DNS 解析

## 校验配置

x86_64 VPS：

```bash
/root/Projects/20260515-mimo443/mimo-linux-amd64 \
  -d /root/Projects/20260515-mimo443 \
  -t -f /root/Projects/20260515-mimo443/config.yaml
```

ARM64：

```bash
/root/Projects/20260515-mimo443/mimo-linux-arm64-a53 \
  -d /root/Projects/20260515-mimo443 \
  -t -f /root/Projects/20260515-mimo443/config.yaml
```

成功输出应包含：

```text
configuration file ... test is successful
```

## 验证国内外分流

推荐用 controller 看规则命中：

```bash
curl -s http://127.0.0.1:19093/proxies
curl -s http://127.0.0.1:19093/rules
```

不要在日志里打印代理密码。可用 Python 从 `config.yaml` 读取 2002 入口认证并测试：

```bash
python3 - <<'PY'
import base64, json, socket, ssl, urllib.request, yaml
from pathlib import Path
cfg = yaml.safe_load(Path('/root/Projects/20260515-mimo443/config.yaml').read_text())
listener = next(x for x in cfg.get('listeners', []) if int(x.get('port', 0)) == 2002)
user = (listener.get('users') or [{}])[0]
auth = base64.b64encode(f"{user.get('username','')}:{user.get('password','')}".encode()).decode()

def head(host, path='/'):
    s = socket.create_connection(('127.0.0.1', 2002), timeout=8)
    s.sendall((f'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\nProxy-Authorization: Basic {auth}\r\n\r\n').encode())
    first = s.recv(4096).decode('latin1', 'replace').split('\r\n', 1)[0]
    if ' 200 ' not in first:
        print(host, first)
        return
    tls = ssl.create_default_context().wrap_socket(s, server_hostname=host)
    tls.sendall(f'HEAD {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n'.encode())
    print(host, tls.recv(4096).decode('latin1', 'replace').split('\r\n', 1)[0])
    tls.close()

head('www.baidu.com', '/')
head('www.qq.com', '/')
head('www.google.com', '/generate_204')
head('www.cloudflare.com', '/')
PY
```

健康状态示例：

```text
www.baidu.com HTTP/1.1 200 OK
www.qq.com HTTP/1.1 200 OK
www.google.com HTTP/1.1 204 No Content
www.cloudflare.com HTTP/1.1 200 OK
```

规则命中期望：

```text
direct 命中增加：国内站点正常直连
proxy 命中增加：国外站点正常走节点
MATCH 不应大量增加：说明主要命中规则集，不是全靠兜底
```

## 给 VPS 工具使用代理

临时当前 shell：

```bash
export http_proxy="http://用户名:密码@127.0.0.1:2002"
export https_proxy="$http_proxy"
export HTTP_PROXY="$http_proxy"
export HTTPS_PROXY="$http_proxy"
export no_proxy="localhost,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
export NO_PROXY="$no_proxy"
```

APT：

```bash
cat >/etc/apt/apt.conf.d/99proxy <<'EOF'
Acquire::http::Proxy "http://用户名:密码@127.0.0.1:2002";
Acquire::https::Proxy "http://用户名:密码@127.0.0.1:2002";
EOF
```

取消 APT 代理：

```bash
rm -f /etc/apt/apt.conf.d/99proxy
```

npm：

```bash
npm config set proxy "http://用户名:密码@127.0.0.1:2002"
npm config set https-proxy "http://用户名:密码@127.0.0.1:2002"
```

取消 npm 代理：

```bash
npm config delete proxy
npm config delete https-proxy
```

systemd 服务单独设置，以 Docker 为例：

```bash
mkdir -p /etc/systemd/system/docker.service.d
cat >/etc/systemd/system/docker.service.d/http-proxy.conf <<'EOF'
[Service]
Environment="HTTP_PROXY=http://用户名:密码@127.0.0.1:2002"
Environment="HTTPS_PROXY=http://用户名:密码@127.0.0.1:2002"
Environment="NO_PROXY=localhost,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
EOF
systemctl daemon-reload
systemctl restart docker
```

不要盲目写 `/etc/environment`。全局环境变量会影响所有进程，代理入口或认证异常时可能造成“整台 VPS 没网”。优先按软件单独配置。

## VPS 透明代理（iptables REDIRECT）

除了 HTTP 入口代理，还可以做整机透明代理：所有本机出站 TCP 流量自动走 mimo，无需设置 `http_proxy` 环境变量。

### 原理

```text
本机程序出站 TCP
  -> iptables OUTPUT/PREROUTING NAT 链
  -> MIMO_REDIR 自定义链
  -> 跳过：routing-mark（mimo自身流量）、保留地址、mimo端口
  -> DNS :53 重定向到 mimo :1053
  -> 其余 TCP 重定向到 mimo :7892（redir-port）
  -> mimo 按规则分流：CN 直连，国外走节点
```

参考 ShellCrash 的 iptables REDIRECT 模式，核心是用 `iptables -t nat -j REDIRECT` 把流量导入 mimo 的 redir 端口。

### 文件

```text
tproxy.sh                iptables 规则管理脚本（start/stop/status）
/etc/systemd/system/mimo-tproxy.service   systemd 服务，依赖 mimo.service
```

### config.yaml 新增配置

```yaml
redir-port: 7892          # iptables REDIRECT 目标端口
routing-mark: 255          # 防回环标记，mimo 出站流量带此 mark
dns:
  listen: 0.0.0.0:1053    # DNS 监听端口，iptables 劫持 :53 到此
```

`routing-mark` 是关键：mimo 发起的出站连接会带上 `fwmark=255`，iptables 规则遇到 `--mark 255` 直接 RETURN，防止 mimo 流量被自己劫持形成回环。

### 防回环机制

```text
mimo 出站 -> 内核标记 fwmark=255
iptables MIMO_REDIR 链第一条：
  -m mark --mark 0xff -j RETURN   # 跳过 mimo 自身流量
```

ShellCrash 用 `--gid-owner 7890`（专用 GID）防回环。本方案用 `routing-mark`，更简单，不需要改 mimo 运行用户。

### iptables 规则详解

```bash
# 创建自定义链
iptables -t nat -N MIMO_REDIR

# 防回环
iptables -t nat -A MIMO_REDIR -m mark --mark 255 -j RETURN

# 跳过 mimo 相关端口（避免 loop）
iptables -t nat -A MIMO_REDIR -p tcp -m multiport --dports 2002,19093,7892,1053 -j RETURN
iptables -t nat -A MIMO_REDIR -p udp -m multiport --dports 2002,19093,7892,1053 -j RETURN

# 跳过保留/私有地址
iptables -t nat -A MIMO_REDIR -d 127.0.0.0/8 -j RETURN
iptables -t nat -A MIMO_REDIR -d 10.0.0.0/8 -j RETURN
# ... 其他 RFC1918 地址

# DNS 劫持（放 TCP 前面，避免被 TCP 规则吃掉）
iptables -t nat -A MIMO_REDIR -p tcp --dport 53 -j REDIRECT --to-ports 1053
iptables -t nat -A MIMO_REDIR -p udp --dport 53 -j REDIRECT --to-ports 1053

# TCP 全部重定向到 mimo redir 端口
iptables -t nat -A MIMO_REDIR -p tcp -j REDIRECT --to-ports 7892

# 挂载到 OUTPUT（本机流量）和 PREROUTING（其他设备流量）
iptables -t nat -I OUTPUT -p tcp -j MIMO_REDIR
iptables -t nat -I OUTPUT -p udp --dport 53 -j MIMO_REDIR
iptables -t nat -I PREROUTING -p tcp -j MIMO_REDIR
iptables -t nat -I PREROUTING -p udp --dport 53 -j MIMO_REDIR
```

### 启用

```bash
# 确保 mimo 已启动且 redir-port 监听
ss -lntup | grep 7892

# 启动透明代理
systemctl enable --now mimo-tproxy.service

# 验证
bash /root/Projects/20260515-mimo443/tproxy.sh status
```

### 验证

```bash
# DNS 劫持生效
dig +short google.com          # 应返回正确 IP

# 国外走代理
curl -s -o /dev/null -w "%{http_code}" https://www.google.com   # 200/302

# 国内直连
curl -s -o /dev/null -w "%{http_code}" https://www.baidu.com    # 200

# 查看 iptables 规则
iptables -t nat -L MIMO_REDIR -n -v
```

### 停用

```bash
systemctl disable --now mimo-tproxy.service
# 或手动
bash /root/Projects/20260515-mimo443/tproxy.sh stop
```

### 局限

- 只劫持 TCP + DNS。UDP（如 QUIC/HTTP3）不走代理，需 TPROXY 模式。
- 仅 IPv4。IPv6 需额外 ip6tables 规则。
- 不如 TUN 模式全面，但零内核模块依赖，VPS 兼容性最好。

### 与 HTTP 代理的关系

```text
HTTP 代理 (:2002)    手动设置 proxy，按需使用
透明代理 (iptables)  自动劫持，无需配置，整机生效
```

两者并存不冲突。透明代理让 VPS 上所有程序（cron、systemd 服务、apt 等）自动走分流，不需逐个配置代理环境变量。

## Claude Code 使用代理

如果需要 Claude Code 和后续网络工具走本代理，把代理 env 写入：

```text
/root/.claude/settings.json
```

字段：

```json
{
  "env": {
    "HTTP_PROXY": "http://用户名:密码@127.0.0.1:2002",
    "HTTPS_PROXY": "http://用户名:密码@127.0.0.1:2002",
    "http_proxy": "http://用户名:密码@127.0.0.1:2002",
    "https_proxy": "http://用户名:密码@127.0.0.1:2002",
    "ALL_PROXY": "http://用户名:密码@127.0.0.1:2002",
    "all_proxy": "http://用户名:密码@127.0.0.1:2002",
    "NO_PROXY": "localhost,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
    "no_proxy": "localhost,127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
  }
}
```

不要把真实密码提交到项目 README。要自动写入时，从 `config.yaml` 读取并 URL encode 后写入 settings，输出时脱敏。

## 安全注意

1. `2000` 控制台默认公网监听。生产建议改为只监听 `127.0.0.1`，再用 HTTPS 反代或 SSH 隧道访问。
2. `2002` HTTP 入口公网开放时必须使用强用户名密码。
3. 控制台可改配置并 reload/restart 服务，不要暴露给不可信网络。
4. `config.yaml`、`console-auth.yaml` 权限应保持 `600`。
5. 不要在聊天、README、提交、日志中泄露代理密码、节点密码、控制台密码。

## 故障排查

服务状态：

```bash
systemctl status --no-pager --lines=80 mimo.service mimo-console.service
journalctl -u mimo.service -u mimo-console.service --no-pager -n 120
```

端口：

```bash
ss -lntup | grep -E ':(2000|2002|19093|7892|1053)\b'
```

配置校验：

```bash
/root/Projects/20260515-mimo443/mimo-linux-amd64 -d /root/Projects/20260515-mimo443 -t -f /root/Projects/20260515-mimo443/config.yaml
```

规则下载失败：

```text
检查 x-split-route 是否 true
检查 rule-providers 是否存在 proxy: 节点选择
检查 节点选择 当前节点是否可用
检查 ruleset/ 下 direct.yaml、proxy.yaml、cncidr.yaml 是否存在/更新
```

代理返回 407：

```text
客户端没有带 Proxy-Authorization
用户名或密码错误
代理 URL 中特殊字符没有 URL encode
```

Google 不通、国内通：

```text
检查 节点选择 当前节点
检查 controller /proxies 里节点延迟/状态
尝试切换节点并 reload
```

国内走代理：

```text
检查 direct/cncidr 规则是否加载
检查规则顺序是否是 proxy -> direct -> cncidr -> MATCH
检查目标域名是否在 proxy 规则集中
```

## 删除

停止并禁用：

```bash
systemctl disable --now mimo-tproxy.service mimo-console.service mimo.service
```

菜单删除全部：

```bash
bash /root/Projects/20260515-mimo443/start.sh
# 选择 6
```

手动删除 systemd：

```bash
rm -f /etc/systemd/system/mimo.service /etc/systemd/system/mimo-console.service /etc/systemd/system/mimo-tproxy.service
systemctl daemon-reload
```

## 控制台安全加固 (fail2ban)

控制台监听 `0.0.0.0:2000`，建议配置 fail2ban 自动封禁暴力破解 IP。

**快速配置:**

```bash
cd /root/projects/20260515-mimo443
bash fail2ban-setup.sh
```

**封禁策略:**
- 10 分钟内 3 次认证失败 → 封禁 10 分钟
- 封禁可自定义为渐进式 (首次 10 分钟，再犯 1 小时，永久封禁)

**手动管理:**

```bash
# 查看封禁列表
fail2ban-client status mimo-console

# 解封 IP
fail2ban-client set mimo-console unbanip 1.2.3.4

# 封禁 IP
fail2ban-client set mimo-console banip 1.2.3.4

# 查看日志
journalctl -u fail2ban -f
```

**认证失败日志格式:**
```
[AUTH_FAIL] 1.2.3.4 - Authorization failed
```

fail2ban 监控此日志自动触发 iptables 封禁。
