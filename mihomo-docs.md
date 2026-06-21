# mihomo (虚空终端) 完整文档

> **版本**: v1.19.27 · **项目**: MetaCubeX/mihomo · **来源**: https://wiki.metacubex.one/ · **蒸馏时间**: 2026-06-17  
> 基于开源项目 原神(clash) 的二次开发版本，增加独有特性。

---

## 1. 项目简介

**虚空终端** 是一个基于开源项目原神 (clash) 的二次开发版本，增加了一些独有特性。

- 支持原神的全部特性，支持原神 Premium 核心部分特性
- 文档基于 Alpha 分支介绍
- 文档仍在修订中，欢迎 PR

---

## 2. 安装与启动

### 2.1 安装方式

请查阅 https://wiki.metacubex.one/startup/ 获取详细安装教程。

### 2.2 客户端/Web 面板/服务管理

| 资源 | 说明 |
|------|------|
| [客户端](https://wiki.metacubex.one/startup/client/) | 各平台客户端安装 |
| [三方客户端](https://wiki.metacubex.one/startup/client/client/) | 第三方工具/客户端列表 |
| [Web 面板](https://wiki.metacubex.one/startup/web/) | Web 管理面板配置 |
| [创建服务](https://wiki.metacubex.one/startup/service/) | 系统服务创建 |

---

## 3. 配置文件语法

mihomo 使用 YAML 作为配置文件格式。

### 3.1 基本语法

- 大小写敏感
- 缩进使用空格（不能用 tab）
- `#` 开头为注释
- `key: value` 键值对（冒号后需空格）
- `-` 开头表示数组元素
- 可直接使用 JSON 格式

### 3.2 引用与锚点

```yaml
p: &p
  type: http
  interval: 3600
  health-check:
    enable: true
    url: https://www.gstatic.com/generate_204
    interval: 300

proxy-providers:
  provider1:
    <<: *p
    url: ""
    path: ./provider1.yaml
```

### 3.3 域名通配符

| 符号 | 说明 |
|------|------|
| `*` | 匹配一级域名，`*.baidu.com` 匹配 `tieba.baidu.com` |
| `+` | 匹配多级域名，`+.baidu.com` 匹配 `tieba.baidu.com` 和 `baidu.com` |
| `.` | 匹配多级域名但**不**匹配根域名 |

### 3.4 端口范围

使用 `-` 匹配范围，`/` 或 `,` 区分多组：`114-514/810-1919,65530`

---

## 4. 快速配置示例

```yaml
port: 7890
socks-port: 7891
allow-lan: false
mode: Rule
log-level: info
external-controller: 127.0.0.1:9090
external-ui: ui
secret: ""
```

---

## 5. 全局配置

```yaml
mixed-port: 7890           # 混合代理端口（HTTP+SOCKS）
port: 7890                  # HTTP 代理端口
socks-port: 7891            # SOCKS5 代理端口
allow-lan: false            # 允许局域网连接
bind-address: "*"           # 绑定地址
mode: Rule                  # Rule/Global/Direct
log-level: info             # silent/info/warning/error/debug
ipv6: false                  # 启用 IPv6
external-controller: 127.0.0.1:9090  # RESTful API
external-ui: ui             # Web 面板目录
secret: ""                  # API 密钥
interface-name: eth0        # 默认绑定的接口
routing-mark: 6666          # 默认路由标记
tcp-concurrent: false       # TCP 并发
keep-alive-interval: 30     # TCP Keep-Alive 间隔
find-process-mode: strict   # 进程匹配模式（off/static/strict）
global-client-fingerprint: chrome  # 全局 TLS 指纹
global-ua: ""               # 全局 User-Agent
unified-delay: false        # 统一延迟（tcp+udp）
```

---

## 6. DNS 配置

### 6.1 完整配置

```yaml
dns:
  enable: true
  cache-algorithm: arc       # lru(默认) / arc
  prefer-h3: false            # DoH 优先 HTTP/3
  use-hosts: true
  use-system-hosts: true
  respect-rules: false
  listen: 0.0.0.0:1053
  ipv6: false
  default-nameserver:
    - 223.5.5.5
  enhanced-mode: fake-ip      # fake-ip / redir-host
  fake-ip-range: 198.18.0.1/16
  fake-ip-range6: fdfe:dcba:9876::1/64
  fake-ip-filter-mode: blacklist  # blacklist/whitelist/rule
  fake-ip-filter:
    - '*.lan'
  fake-ip-ttl: 1
  nameserver-policy:
    '+.arpa': '10.0.0.1'
    'rule-set:cn':
      - https://doh.pub/dns-query
      - https://dns.alidns.com/dns-query
  nameserver:
    - https://doh.pub/dns-query
    - https://dns.alidns.com/dns-query
  fallback:
    - tls://8.8.4.4
    - tls://1.1.1.1
  proxy-server-nameserver:
    - https://doh.pub/dns-query
  proxy-server-nameserver-policy:
    'www.yournode.com': '114.114.114.114'
  direct-nameserver:
    - system
  direct-nameserver-follow-policy: false
  fallback-filter:
    geoip: true
    geoip-code: CN
    geosite:
      - gfw
    ipcidr:
      - 240.0.0.0/4
    domain:
      - '+.google.com'
      - '+.facebook.com'
      - '+.youtube.com'
```

### 6.2 DNS 参数说明

| 参数 | 说明 |
|------|------|
| `enable` | 是否启用 mihomo DNS |
| `cache-algorithm` | lru 或 arc 缓存算法 |
| `prefer-h3` | DoH 优先使用 HTTP/3 |
| `enhanced-mode` | `fake-ip` 或 `redir-host` |
| `fake-ip-filter-mode` | blacklist(默认) / whitelist / rule |
| `default-nameserver` | 用于解析 DNS 服务器域名的上游（必须为 IP） |
| `nameserver-policy` | 指定域名的 DNS 服务器，支持 geosite |
| `proxy-server-nameserver` | 代理节点域名解析专用 |
| `direct-nameserver` | direct 出口域名解析专用 |
| `fallback` | 备用 DNS，一般用境外 DNS |
| `fallback-filter` | 备用 DNS 过滤条件 |

### 6.3 DNS 附加参数

在 DNS 服务器 URL 后使用 `#` 附加参数：

```
nameserver:
  - 'https://8.8.8.8/dns-query#proxy&ecs=1.1.1.1/24&ecs-override=true'
```

| 参数 | 说明 |
|------|------|
| `proxy` | 指定代理名称连接 |
| `RULES` | 遵守路由规则连接 |
| `h3` | 强制 HTTP/3 |
| `skip-cert-verify` | 跳过证书验证 |
| `ecs` | 指定 ECS subnet |
| `ecs-override` | 强制覆盖 ECS |
| `disable-ipv4` | 丢弃 A 记录 |
| `disable-ipv6` | 丢弃 AAAA 记录 |

### 6.4 DNS Hosts

```yaml
dns:
  hosts:
    '*.example.com': 1.1.1.1
    '.dev': 127.0.0.1
    'alpha.mihomo': 127.0.0.1
```

---

## 7. 域名嗅探

```yaml
sniffer:
  enable: false
  force-dns-mapping: true
  parse-pure-ip: true
  override-destination: false
  sniff:
    HTTP:
      ports: [80, 8080-8880]
      override-destination: true
    TLS:
      ports: [443, 8443]
    QUIC:
      ports: [443, 8443]
  force-domain:
    - +.v2ex.com
  skip-domain:
    - Mijia Cloud
  skip-src-address:
    - 192.168.0.3/32
  skip-dst-address:
    - 192.168.0.3/32
```

---

## 8. 入站 (Inbound)

### 8.1 快速端口

```yaml
mixed-port: 7890     # HTTP + SOCKS
port: 7890           # HTTP
socks-port: 7891     # SOCKS4/5
```

### 8.2 TUN 入站

```yaml
tun:
  enable: true
  stack: system          # system / gvisor / mixed / lwip
  dns-hijack:
    - any:53
  auto-route: true
  auto-redirect: true    # Linux TCP 重定向
  strict-route: true
  mtu: 9000
  gso: true
  device: utun
  endpoint-independent-nat: true
  udp-timeout: 300
  route-address:
    - 0.0.0.0/0
  exclude-interface:
    - docker0
```

### 8.3 Listeners（自定义入站）

```yaml
listeners:
- name: in-name          # 入站名称
  type: shadowsocks      # 入站类型
  port: 10000
  listen: 0.0.0.0
  rule: sub-rule-1       # 可选，使用子规则
  proxy: proxy           # 可选，直接指定出站
```

| 监听类型 | 说明 |
|----------|------|
| `http` | HTTP 代理 |
| `socks` | SOCKS 代理 |
| `mixed` | HTTP + SOCKS 混合 |
| `redirect` | 透明代理重定向 |
| `tproxy` | 透明代理 TProxy |
| `tun` | TUN 虚拟网卡 |
| `shadowsocks` | Shadowsocks |
| `vmess` | VMess |
| `vless` | VLESS |
| `trojan` | Trojan |
| `anytls` | AnyTLS |
| `mieru` | Mieru |
| `sudoku` | Sudoku |
| `tuic-v4` | TUIC v4 |
| `tuic-v5` | TUIC v5 |
| `hysteria2` | Hysteria2 |
| `hysteria2-realm` | Hysteria2 Realm |
| `trusttunnel` | TrustTunnel |
| `tunnel` | 隧道 |
| `snell` | Snell |

---

## 9. 出站代理 (Proxies)

### 9.1 通用字段

```yaml
proxies:
- name: "ss"
  type: ss
  server: server
  port: 443
  ip-version: ipv4          # dual/ipv4/ipv6/ipv4-prefer/ipv6-prefer
  udp: true
  interface-name: eth0
  routing-mark: 1234
  tfo: false
  mptcp: false
  dialer-proxy: ss1          # 通过另一代理建立连接
  smux:
    enabled: true
    protocol: h2mux          # smux/yamux/h2mux
    max-connections: 4
    min-streams: 4
    max-streams: 0
    padding: true
    brutal-opts:
      enabled: true
      up: 50
      down: 100
```

### 9.2 代理类型

| 类型 | 说明 |
|------|------|
| `direct` | 直连 |
| `dns` | DNS 出站 |
| `http` | HTTP 代理 |
| `socks` | SOCKS5 代理 |
| `shadowsocks` | Shadowsocks |
| `shadowsocksr` | ShadowsocksR |
| `snell` | Snell |
| `vmess` | VMess |
| `vless` | VLESS |
| `trojan` | Trojan |
| `anytls` | AnyTLS |
| `mieru` | Mieru |
| `sudoku` | Sudoku |
| `hysteria` | Hysteria 1 |
| `hysteria2` | Hysteria 2 |
| `tuic` | TUIC |
| `wireguard` | WireGuard |
| `tailscale` | Tailscale |
| `ssh` | SSH |
| `masque` | MASQUE |
| `trusttunnel` | TrustTunnel |
| `openvpn` | OpenVPN |

### 9.3 TLS 配置

```yaml
proxies:
- name: "tls-example"
  type: trojan
  tls: true
  servername: example.com
  skip-cert-verify: false
  fingerprint: chrome       # TLS 指纹
  alpn: [h2, http/1.1]
  reality:                  # Reality 配置
    public-key: ""
    short-id: ""
```

### 9.4 传输层配置

| 传输类型 | 字段 | 说明 |
|----------|------|------|
| HTTP | `network: http` | `http-opts` 配置 method/path/headers |
| H2 | `network: h2` | `h2-opts` 配置 host/path |
| gRPC | `network: grpc` | `grpc-opts` 配置 service-name |
| WebSocket | `network: ws` | `ws-opts` 配置 path/headers/max-early-data |
| XHTTP | `network: xhttp` | `xhttp-opts` 新协议 |

### 9.5 内置代理策略

| 策略 | 说明 |
|------|------|
| `direct` | 直连 |
| `bypass` | 绕过所有规则 |
| `dns` | DNS 查询专用 |
| `reject` | 拒绝连接 |

### 9.6 dialer-proxy

允许代理链——让一个代理通过另一个代理建立连接，可用于多层代理场景。

---

## 10. 代理集合 (Proxy Provider)

```yaml
proxy-providers:
  provider1:
    type: http               # http / file
    url: "https://..."
    path: ./provider1.yaml
    interval: 3600           # 更新间隔（秒）
    proxy: DIRECT            # 通过指定代理更新
    header:
      User-Agent:
      - "mihomo/1.19.27"
    filter: "香港"
    exclude-filter: "日本"
```

### 代理集合内容

支持多行 YAML 或单行 proxy 格式，包含 `proxies:` 列表。

---

## 11. 代理组 (Proxy Group)

### 11.1 通用字段

```yaml
proxy-groups:
- name: "proxy"
  type: select
  proxies:
  - DIRECT
  - ss
  use:
  - provider1
  url: 'https://www.gstatic.com/generate_204'
  interval: 300
  lazy: true
  empty-fallback: COMPATIBLE
  timeout: 5000
  max-failed-times: 5
  disable-udp: true
  include-all: false
  include-all-proxies: false
  include-all-providers: false
  filter: "(?i)港|hk|hongkong|hong kong"
  exclude-filter: "美|日"
  exclude-type: "Shadowsocks|Http"
  expected-status: 204
  hidden: true
  icon: xxx
```

### 11.2 策略组类型

| 类型 | 说明 |
|------|------|
| `select` | 手动选择 |
| `url-test` | 自动选择（延迟测试） |
| `fallback` | 自动回退（按优先级） |
| `load-balance` | 负载均衡 |
| `relay` | 链式代理 |
| `direct` | 内置直连 |
| `dns` | 内置 DNS |
| `bypass` | 内置绕过 |
| `reject` | 内置拒绝 |
| `compatible` | 兼容模式 |
| `pass` | 直通 |

### 11.3 筛选与排除

- `filter`: 正则筛选节点名称
- `exclude-filter`: 正则排除节点名称
- `exclude-type`: 按类型排除（`|` 分隔）
- `include-all`: 引入所有出站代理和代理集合
- `include-all-proxies`: 仅引入出站代理
- `include-all-providers`: 仅引入代理集合

---

## 12. 路由规则

### 12.1 规则语法

```yaml
rules:
- DOMAIN,ad.com,REJECT
- DOMAIN-SUFFIX,google.com,auto
- DOMAIN-KEYWORD,google,auto
- DOMAIN-WILDCARD,*.google.com,auto
- DOMAIN-REGEX,^abc.*com,PROXY
- GEOSITE,youtube,PROXY
- IP-CIDR,127.0.0.0/8,DIRECT,no-resolve
- IP-CIDR6,2620:0:2d0:200::7/32,auto
- IP-SUFFIX,8.8.8.8/24,PROXY
- IP-ASN,13335,DIRECT
- GEOIP,CN,DIRECT
- SRC-GEOIP,cn,DIRECT
- SRC-IP-ASN,9808,DIRECT
- SRC-IP-CIDR,192.168.1.201/32,DIRECT
- DST-PORT,80,DIRECT
- SRC-PORT,7777,DIRECT
- IN-PORT,7890,PROXY
- IN-TYPE,SOCKS/HTTP,PROXY
- IN-USER,mihomo,PROXY
- IN-NAME,ss,PROXY
- PROCESS-PATH,/usr/bin/wget,PROXY
- PROCESS-PATH-WILDCARD,/usr/*/wget,PROXY
- PROCESS-PATH-REGEX,.*bin/wget,PROXY
- PROCESS-NAME,curl,PROXY
- PROCESS-NAME-WILDCARD,*telegram*,PROXY
- PROCESS-NAME-REGEX,(?i)Telegram,PROXY
- UID,1001,DIRECT
- NETWORK,udp,DIRECT
- DSCP,4,DIRECT
- RULE-SET,providername,proxy
- AND,((DOMAIN,baidu.com),(NETWORK,UDP)),DIRECT
- OR,((NETWORK,UDP),(DOMAIN,baidu.com)),REJECT
- NOT,((DOMAIN,baidu.com)),PROXY
- SUB-RULE,(NETWORK,tcp),sub-rule
- MATCH,auto
```

### 12.2 规则类型说明

| 规则 | 说明 |
|------|------|
| `DOMAIN` | 完整域名匹配 |
| `DOMAIN-SUFFIX` | 域名后缀匹配 |
| `DOMAIN-KEYWORD` | 域名关键字匹配 |
| `DOMAIN-WILDCARD` | 通配符（`*` `?`） |
| `DOMAIN-REGEX` | 正则表达式匹配 |
| `GEOSITE` | Geosite 数据库匹配 |
| `IP-CIDR` / `IP-CIDR6` | IP 段匹配 |
| `IP-SUFFIX` | IP 后缀范围 |
| `IP-ASN` | ASN 编号 |
| `GEOIP` | 国家 IP 匹配 |
| `SRC-GEOIP` | 来源国家 IP |
| `SRC-IP-ASN` | 来源 ASN |
| `SRC-IP-CIDR` / `SRC-IP-SUFFIX` | 来源 IP 段 |
| `DST-PORT` | 目标端口 |
| `SRC-PORT` | 来源端口 |
| `IN-PORT` | 入站端口 |
| `IN-TYPE` | 入站类型 |
| `IN-USER` | 入站用户名 |
| `IN-NAME` | 入站名称 |
| `PROCESS-PATH` | 进程路径 |
| `PROCESS-NAME` | 进程名/Android 包名 |
| `UID` | Linux 用户 ID |
| `NETWORK` | TCP/UDP 协议 |
| `DSCP` | DSCP 标记（仅 tproxy udp） |
| `RULE-SET` | 引用规则集合 |
| `AND` / `OR` / `NOT` | 逻辑组合 |
| `SUB-RULE` | 子规则跳转 |
| `MATCH` | 全匹配（兜底） |

### 12.3 参数

- `no-resolve`: 跳过 DNS 解析
- `src`: 将目标 IP 匹配转为来源 IP 匹配

优先级：从上到下，顶部规则优先级最高。

---

## 13. 规则集合 (Rule Provider)

```yaml
rule-providers:
  google:
    type: http               # http / file / inline
    url: "https://..."
    path: ./rule1.yaml
    interval: 600
    proxy: DIRECT
    behavior: classical      # domain / ipcidr / classical
    format: yaml             # yaml / text / mrs
    size-limit: 0            # 最大下载字节数（0=不限）
    header:
      Authorization:
      - 'token 1231231'
    payload:                 # inline 类型使用
      - 'DOMAIN-SUFFIX,google.com'
```

支持 ruleset 转换：`mihomo convert-ruleset domain/ipcidr yaml/text XXX.yaml XXX.mrs`

---

## 14. 子规则

```yaml
sub-rules:
  rule1:
    - DOMAIN-SUFFIX,baidu.com,DIRECT
    - MATCH,PROXY
  sub-rule2:
    - IP-CIDR,1.1.1.1/32,REJECT
    - IP-CIDR,8.8.8.8/32,ss1
    - DOMAIN,dns.alidns.com,REJECT
```

子规则可通过入站的 `rule` 字段或 `SUB-RULE` 规则引用。

---

## 15. 流量隧道 (Tunnel)

```yaml
tunnels:
- tcp/udp,127.0.0.1:6553,114.114.114.114:53,proxy
```

| 参数 | 说明 |
|------|------|
| `network` | tcp/udp |
| `address` | 本地监听地址 |
| `target` | 转发目标 |
| `proxy` | 可选，经过的出站/策略组 |

---

## 16. NTP

```yaml
ntp:
  enable: true
  write-to-system: true      # 同步至系统时间
  server: time.apple.com
  port: 123
  interval: 30               # 同步间隔（分钟）
  dialer-proxy: DIRECT
```

---

## 17. RESTful API

### API 基础

```bash
curl -H 'Authorization: Bearer <secret>' http://${controller-api}/configs?force=true -X PUT -d '{"path": "", "payload": ""}'
```

### API 端点

| 路径 | 方法 | 说明 |
|------|------|------|
| `/logs` | GET/WS | 实时日志 |
| `/traffic` | GET/WS | 实时流量 |
| `/memory` | GET/WS | 内存占用 |
| `/version` | GET | 版本信息 |
| `/cache/fakeip/flush` | POST | 清除 fakeip 缓存 |
| `/cache/dns/flush` | POST | 清除 DNS 缓存 |
| `/configs` | GET/PUT/PATCH | 运行配置 |
| `/configs/geo` | POST | 更新 GEO 数据库 |
| `/restart` | POST | 重启内核 |
| `/upgrade` | POST | 更新内核 |
| `/upgrade/ui` | POST | 更新面板 |
| `/upgrade/geo` | POST | 更新 GEO 数据库 |
| `/group` | GET | 策略组信息 |
| `/group/:name` | GET/DELETE | 具体策略组 |
| `/group/:name/delay` | GET | 策略组延迟测试 |
| `/proxies` | GET | 代理信息 |
| `/proxies/:name` | GET/PUT | 具体代理/切换 |
| `/proxies/:name/delay` | GET | 代理延迟测试 |
| `/providers/proxies` | GET | 代理集合信息 |
| `/providers/proxies/:name` | GET/PUT | 具体代理集合/更新 |
| `/providers/proxies/:name/healthcheck` | GET | 触发健康检查 |
| `/rules` | GET | 规则信息 |
| `/rules/disable` | PATCH | 禁用/启用规则 |
| `/providers/rules` | GET | 规则集合信息 |
| `/providers/rules/:name` | PUT | 更新规则集合 |
| `/connections` | GET/WS/DELETE | 连接信息/关闭全部 |
| `/connections/:id` | DELETE | 关闭特定连接 |
| `/dns/query` | GET | DNS 查询 |
| `/debug/gc` | PUT | 主动 GC |
| `/debug/pprof` | GET | pprof 性能分析 |

---

*文档来源：https://wiki.metacubex.one/ · 由 AI 蒸馏整理 · v1.19.27*