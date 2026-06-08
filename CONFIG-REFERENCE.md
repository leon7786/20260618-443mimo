# MetaCubeX Mihomo 配置完整参考

> 来源: https://wiki.metacubex.one/config/
> 格式: AI 可解析参考规则

---

## 1. 顶级配置

```yaml
# 必填
mode: rule                   # rule / global / direct
log-level: info              # error / warning / info / debug

# 网络
ipv6: false                  # 是否启用 IPv6
allow-lan: false             # 是否允许局域网连接
bind-address: "*"            # 绑定地址
tcp-concurrent: true         # TCP 并发连接 (同目标多 IP 并发)
unified-delay: true          # 统一延迟计算
connection-timeout: 5        # 连接超时 (秒)
keep-alive-interval: 30      # 长连接心跳间隔 (秒)
keep-alive-idle: 600         # 长连接空闲超时 (秒)

# 端口 (至少设一个非零端口, 否则内核不处理流量)
port: 0                      # HTTP 代理端口
socks-port: 0                # SOCKS5 代理端口
mixed-port: 0                # HTTP+SOCKS 混合端口
redir-port: 0                # 透明代理 REDIRECT 端口
tproxy-port: 0               # 透明代理 TPROXY 端口

# 管理
external-controller: 0.0.0.0:9090  # RESTful API 监听
secret: ""                   # API 密钥

# Geo 数据
geodata-mode: false          # false=rule-providers, true=内置 geo 文件
geodata-loader: memconservative  # memconservative / standard
geo-auto-update: false       # 自动更新 geo 数据
geoip-format: metadb         # dat / metadb

# 性能
routing-mark: 0              # 全局 SO_MARK
interface-name: ""           # 全局出站网卡
```

**规则**: `mode: rule` 时按 rules 列表匹配; `global` 时全部走 MATCH; `direct` 时全部直连。

---

## 2. Listeners (入站)

所有入站通用字段:
```yaml
listeners:
  - name: listener-name       # 必填, 唯一
    type: http                # 必填, 类型
    port: 10809               # 必填
    listen: 0.0.0.0           # 默认 0.0.0.0
    udp: true                 # 默认 true
    proxy: proxy-name         # 跳过规则, 直接交给指定 proxy
    rule: sub-rule-name       # 使用子规则代替 rules
```

### 2.1 局域网入站 (无加密)

| type | 说明 | 特殊字段 |
|------|------|----------|
| `socks` | SOCKS5 代理 | `users: [{username, password}]` |
| `http` | HTTP 代理 | `users: [{username, password}]` |
| `mixed` | HTTP + SOCKS 混合 | 同上 |
| `redir` | REDIRECT 透明代理 | - |
| `tproxy` | TPROXY 透明代理 | - |
| `tun` | 虚拟网卡 TUN | `inet4-address`, `mtu`, `auto-route`, `auto-detect-interface` |

### 2.2 互联网入站 (加密, 可作服务端)

| type | 特殊字段 |
|------|----------|
| `shadowsocks` | `cipher`, `password` |
| `vmess` | `users: [{username, uuid, alterId}]` |
| `tuic` | `users: {uuid: password}` 或 `token: [TOKEN]`, `certificate`, `private-key`, `congestion-controller: bbr`, `alpn: [h3]` |
| `hysteria2` | `users: {name: password}`, `up`, `down`, `obfs: salamander`, `obfs-password`, `certificate`, `private-key` |
| `anytls` | `users: {name: password}`, `certificate`, `private-key`, `padding-scheme` |

**规则**: `proxy` 不为空时跳过路由规则直接转发; `rule` 引用子规则集, 找不到则用默认 rules。

---

## 3. Proxies (出站代理)

### 3.1 通用字段

```yaml
proxies:
  - name: proxy-name          # 必填, 唯一, 不可重复
    type: ss                  # 必填, 协议类型
    server: 1.2.3.4           # 必填, 域名或 IP
    port: 443                 # 必填
    ip-version: dual          # dual / ipv4 / ipv6 / ipv4-prefer / ipv6-prefer
    udp: false                # 是否允许 UDP, TUIC/Hysteria2 默认 true
    tfo: false                # TCP Fast Open
    mptcp: false              # MultiPath TCP
    interface-name: eth0      # 出站网卡
    routing-mark: 1234        # SO_MARK
    dialer-proxy: proxy2      # 通过其他 proxy 建立连接 (链式代理)
    smux:                     # 多路复用 (仅 TCP 传输协议)
      enabled: false
      protocol: h2mux         # smux / yamux / h2mux
      max-connections: 4      # 最大连接数 (与 max-streams 互斥)
      min-streams: 4          # 最小流数 (与 max-streams 互斥)
      max-streams: 0          # 最大流数
      padding: false
      statistic: false        # API 面板中显示底层连接
      only-tcp: false         # 仅对 TCP 生效
      brutal-opts:            # TCP Brutal 拥塞控制
        enabled: false
        up: 50                # 上传带宽 Mbps
        down: 100             # 下载带宽 Mbps
```

**规则**: `dialer-proxy` 实现链式代理, 引用另一个 proxy 或 proxy-group 的 name。

### 3.2 协议速查

| type | 必填字段 | 常用可选字段 |
|------|----------|-------------|
| `ss` | `cipher`, `password` | `udp-over-tcp`, `plugin`, `plugin-opts` |
| `ssr` | `cipher`, `password`, `protocol`, `obfs` | `protocol-param`, `obfs-param` |
| `vmess` | `uuid`, `alterId` | `cipher: auto`, `servername`, `ws-opts`, `grpc-opts` |
| `vless` | `uuid` | `flow: xtls-rprx-vision`, `tls: true`, `reality-opts`, `servername` |
| `trojan` | `password` | `sni`, `skip-cert-verify`, `ws-opts`, `grpc-opts` |
| `tuic` | `uuid`, `password` | `sni`, `alpn: [h3]`, `congestion-controller: bbr`, `skip-cert-verify` |
| `hysteria` | `auth`, `up`, `down` | `sni`, `skip-cert-verify`, `obfs` |
| `hysteria2` | `password` | `sni`, `up`, `down`, `obfs: salamander`, `obfs-password`, `skip-cert-verify` |
| `anytls` | `password` | `sni`, `skip-cert-verify`, `client-fingerprint: chrome`, `alpn` |
| `http` | - | `username`, `password`, `tls` |
| `socks5` | - | `username`, `password`, `tls` |
| `direct` | - | `proxy` (无意义) |
| `dns` | - | DNS 出站专用 |

**规则**: `ip-version` 仅对 `server` 为域名时生效; `dual` = 并发双栈连接选最快; `ipv4-prefer` = 双栈解析但优先 IPv4。

### 3.3 TLS 字段 (https/tls/trojan/vless/tuic/hysteria/anytls 共用)

```yaml
skip-cert-verify: false       # 跳过证书验证
sni: ""                       # TLS SNI
servername: ""                # TLS 服务器名称
alpn: []                      # ALPN 协议列表
client-fingerprint: ""        # TLS 指纹 (chrome/firefox/safari/ios/edge/qq/360)
```

---

## 4. Proxy Groups (代理组)

### 4.1 通用字段

```yaml
proxy-groups:
  - name: group-name          # 必填, 唯一
    type: select              # 必填: select / url-test / fallback / load-balance
    proxies: []               # 引入 proxy 或其他 group 的 name
    use: []                   # 引入 proxy-provider 的 name
    # 健康检查
    url: https://www.gstatic.com/generate_204
    interval: 300             # 秒, 0=不启用定时测试
    timeout: 5000             # 毫秒
    lazy: true                # 未选中时不测试
    max-failed-times: 5       # 最大失败次数, 超则强制健康检查
    expected-status: 204      # 期望 HTTP 状态码, 支持 200/302/400-503 格式
    # 筛选
    filter: "(?i)港|hk"       # 正则筛选节点名
    exclude-filter: "美|日"   # 排除
    exclude-type: "ss|http"   # 按类型排除 (不区分大小写)
    # 其他
    disable-udp: false
    include-all: false        # 引入所有 proxy + provider
    include-all-proxies: false
    include-all-providers: false
    hidden: false             # API 中隐藏
    icon: ""                  # API 中图标标识
```

### 4.2 类型行为

| type | 行为 |
|------|------|
| `select` | 手动选择, 默认用 proxies 列表第一个 |
| `url-test` | 自动选延迟最低的可用节点 |
| `fallback` | 按 proxies 顺序, 选第一个可用的 |
| `load-balance` | 负载均衡轮询 |

**规则**: `filter`/`exclude-filter` 仅对 `use` (代理集合) 和 `include-all-proxies` 生效, 不对 `proxies` 直接引用的生效。

---

## 5. Rules (路由规则)

### 5.1 规则语法: `TYPE,PAYLOAD,TARGET[,PARAM]`

**规则**: 从上到下匹配, 首次命中即停止。如 proxy 不支持 UDP, 则 UDP 继续向下匹配。

### 5.2 规则类型全表

#### 域名类

| 类型 | PAYLOAD | 说明 |
|------|---------|------|
| `DOMAIN` | `google.com` | 精确匹配 |
| `DOMAIN-SUFFIX` | `google.com` | 后缀匹配, 含自身 |
| `DOMAIN-KEYWORD` | `google` | 关键字包含 |
| `DOMAIN-WILDCARD` | `*.google.com` | `*` 和 `?` 通配符 |
| `DOMAIN-REGEX` | `^abc.*com` | 正则匹配 |
| `GEOSITE` | `youtube` | geo 域名集 (需 geodata) |
| `RULE-SET` | `provider-name` | 规则集引用 |

#### IP 类

| 类型 | PAYLOAD | 说明 |
|------|---------|------|
| `IP-CIDR` | `127.0.0.0/8` | IPv4 CIDR |
| `IP-CIDR6` | `2001::/32` | IPv6 CIDR (等同于 IP-CIDR) |
| `IP-SUFFIX` | `8.8.8.8/24` | IP 后缀匹配 |
| `IP-ASN` | `13335` | AS 号匹配 |
| `GEOIP` | `CN` | 国家代码匹配 (需 geodata) |

#### 来源类

| 类型 | PAYLOAD | 说明 |
|------|---------|------|
| `SRC-IP-CIDR` | `192.168.1.0/24` | 来源 IP CIDR |
| `SRC-IP-SUFFIX` | `192.168.1.0/24` | 来源 IP 后缀 |
| `SRC-IP-ASN` | `9808` | 来源 ASN |
| `SRC-GEOIP` | `CN` | 来源国家 |
| `SRC-PORT` | `7777` | 来源端口 (支持范围) |
| `IN-PORT` | `7890` | 入站端口 |
| `IN-TYPE` | `SOCKS/HTTP` | 入站类型 |
| `IN-USER` | `username` | 入站用户名 |
| `IN-NAME` | `ss-in` | 入站 name |
| `PROCESS-PATH` | `/usr/bin/curl` | 进程路径 |
| `PROCESS-PATH-WILDCARD` | `/usr/*/curl` | 进程路径通配符 |
| `PROCESS-PATH-REGEX` | `.*bin/curl` | 进程路径正则 |
| `PROCESS-NAME` | `curl` | 进程名 (Android=包名) |
| `PROCESS-NAME-WILDCARD` | `*telegram*` | 进程名通配符 |
| `PROCESS-NAME-REGEX` | `(?i)Telegram` | 进程名正则 |
| `UID` | `1001` | Linux 用户 ID |

#### 其他

| 类型 | PAYLOAD | 说明 |
|------|---------|------|
| `DST-PORT` | `80` 或 `80,443` 或 `8080-8880` | 目标端口 (支持范围) |
| `NETWORK` | `tcp` / `udp` | 协议类型 |
| `DSCP` | `4` | DSCP 标记 (仅 tproxy UDP) |

#### 逻辑规则

```yaml
- AND,((DOMAIN,baidu.com),(NETWORK,UDP)),DIRECT    # AND: 全部满足
- OR,((NETWORK,UDP),(DOMAIN,baidu.com)),REJECT     # OR: 任一满足
- NOT,((DOMAIN,baidu.com)),PROXY                    # NOT: 取反
- SUB-RULE,(NETWORK,tcp),sub-rule-name             # 引用子规则
```

**规则**: 逻辑规则需要注意括号。`payload` 格式为 `((rule1),(rule2))`, 嵌套时 `((rule1),((rule2),(rule3)))`。

### 5.3 TARGET

| TARGET | 说明 |
|--------|------|
| `proxy-name` | 指向特定 proxy |
| `group-name` | 指向 proxy-group |
| `DIRECT` | 直连 |
| `REJECT` | 拒绝 (TCP=RST, UDP=ICMP port unreachable) |
| `REJECT-DROP` | 静默丢弃 |
| `PASS` | 绕过内核, 由系统协议栈处理 |

### 5.4 PARAM

| 参数 | 适用于 | 说明 |
|------|--------|------|
| `no-resolve` | IP 目标类规则 | 域名时不触发 DNS 解析来匹配此规则 |
| `src` | IP 目标类规则 | 将目标 IP 匹配转为来源 IP 匹配 |

**规则**: 即使加了 `no-resolve`, 如果更早的规则已触发 DNS 解析, 此规则仍会匹配。

---

## 6. DNS

### 6.1 完整配置

```yaml
dns:
  enable: true
  listen: 0.0.0.0:1053
  ipv6: false
  enhanced-mode: redir-host    # redir-host (真实IP) / fake-ip (虚拟IP)
  respect-rules: false         # DNS 查询遵循路由规则
  prefer-h3: false             # DoH 优先 HTTP/3
  cache-algorithm: lru         # lru / arc
  use-hosts: true              # 使用 hosts 配置
  use-system-hosts: true       # 使用系统 /etc/hosts

  default-nameserver:          # 解析 DNS 服务器域名用, 必须为 IP
    - 223.5.5.5
    - 119.29.29.29

  nameserver:                  # 默认 DNS 服务器
    - https://dns.alidns.com/dns-query
    - 223.5.5.5

  proxy-server-nameserver:     # 代理节点域名解析用
    - https://1.1.1.1/dns-query

  proxy-server-nameserver-policy:  # 按节点名指定 DNS
    "www.yournode.com": "114.114.114.114"

  direct-nameserver:           # direct 出口域名解析用
    - system

  direct-nameserver-follow-policy: false  # direct-nameserver 是否遵循 nameserver-policy

  nameserver-policy:           # 按域名/规则集指定 DNS
    "+.arpa": "10.0.0.1"
    "rule-set:cn_domain":
      - https://doh.pub/dns-query
      - https://dns.alidns.com/dns-query

  fallback:                    # 备用 DNS (防止污染)
    - tls://8.8.4.4
    - tls://1.1.1.1

  fallback-filter:             # fallback 触发条件
    geoip: true
    geoip-code: CN
    geosite:
      - gfw
    ipcidr:
      - 240.0.0.0/4
    domain:
      - "+.google.com"
```

### 6.2 enhanced-mode

| 值 | 行为 |
|-----|------|
| `redir-host` | 返回真实 IP, DNS 不篡改 |
| `fake-ip` | 返回虚拟 IP (198.18.0.0/16), 保留域名映射, 配合 TUN 用 |

### 6.3 fake-ip 相关 (仅 enhanced-mode: fake-ip 时生效)

```yaml
fake-ip-range: 198.18.0.1/16
fake-ip-range6: fdfe:dcba:9876::1/64
fake-ip-filter:               # 不返回 fake-ip 的域名列表
  - "*.lan"
  - "+.local"
  - "+.msftconnecttest.com"
fake-ip-filter-mode: blacklist  # blacklist / whitelist / rule
fake-ip-ttl: 1                # fake-ip 记录 TTL
```

**规则**: `fake-ip-filter-mode: rule` 时, filter 写法与路由 rules 一致, 支持 GEOSITE/RULE-SET/DOMAIN*/MATCH, target 为 `fake-ip` 或 `real-ip`。

### 6.4 DNS 服务器附加参数

附加在 DNS 服务器 URL/IP 后, 格式: `dns-server#param1&param2=val`

| 参数 | 说明 |
|------|------|
| `#proxy-name` | 通过指定 proxy 连接 (须已定义) |
| `#RULES` | 遵循路由规则连接 |
| `&h3=true` | 强制 HTTP/3 |
| `&skip-cert-verify=true` | 跳过 TLS 证书验证 |
| `&ecs=1.1.1.1/24` | EDNS Client Subnet |
| `&ecs-override=true` | 强制覆盖 ECS |
| `&disable-ipv4=true` | 丢弃 A 记录 |
| `&disable-ipv6=true` | 丢弃 AAAA 记录 |
| `&disable-qtype-65=true` | 屏蔽 HTTPS (TYPE65) 记录 |

---

## 7. Rule Providers (规则集)

```yaml
rule-providers:
  provider-name:              # 必填, 唯一
    type: http                # 必填: http / file / inline
    behavior: domain          # 必填: domain / ipcidr / classical
    format: mrs               # yaml / text / mrs (默认 yaml)
    url: https://...          # type=http 时必填
    path: ./ruleset/file.mrs  # 缓存路径
    interval: 86400           # 更新间隔 (秒)
    proxy: DIRECT             # 通过代理下载
    size-limit: 0             # 下载大小限制 (字节), 0=不限制
    header:                   # 自定义 HTTP 请求头
      User-Agent: ["mihomo/1.0"]
    payload: []               # type=inline 时直接写规则内容
```

**规则**: 
- `behavior: domain` 用于域名规则 (`DOMAIN-SUFFIX,google.com` 格式)
- `behavior: ipcidr` 用于 IP 规则 (`IP-CIDR,1.0.0.0/8` 格式)  
- `behavior: classical` 用于完整规则 (`DOMAIN-SUFFIX,google.com,PROXY` 格式)
- `format: mrs` 是二进制格式, 更小更快, 由 `mihomo convert-ruleset` 工具生成

### 推荐规则集 URL (MetaCubeX)

| 用途 | behavior | URL |
|------|----------|-----|
| GFW 封锁域名 | domain | `geosite/gfw.mrs` |
| 中国域名 | domain | `geosite/cn.mrs` |
| 中国 IP | ipcidr | `geoip/cn.mrs` |
| 私有域名 | domain | `geosite/private.mrs` |
| Apple 中国 | domain | `geosite/apple-cn.mrs` |
| Steam 中国 | domain | `geosite/steam@cn.mrs` |
| 微软中国 | domain | `geosite/microsoft@cn.mrs` |

基础 URL: `https://cdn.jsdelivr.net/gh/MetaCubeX/meta-rules-dat@meta/geo/`

---

## 8. Proxy Providers (代理集合)

```yaml
proxy-providers:
  provider-name:              # 必填, 唯一
    type: http                # 必填: http / file / inline
    url: https://...          # type=http 时必填
    path: ./proxy_providers/name.yaml
    interval: 3600            # 更新间隔 (秒)
    proxy: DIRECT             # 通过代理下载
    size-limit: 0             # 下载大小限制 (字节)
    header:                   # 自定义 HTTP 请求头
      User-Agent: ["mihomo/1.0"]
      Authorization: ["token xxx"]

    health-check:             # 健康检查
      enable: true
      url: https://www.gstatic.com/generate_204
      interval: 300           # 秒
      timeout: 5000           # 毫秒
      lazy: true              # 未使用时不测试
      expected-status: 204

    override:                 # 覆写节点参数
      udp: true
      skip-cert-verify: true
      dialer-proxy: proxy
      interface-name: eth0
      routing-mark: 233
      ip-version: ipv4-prefer
      additional-prefix: "[prefix] "
      additional-suffix: " [suffix]"
      proxy-name:             # 节点名替换 (正则)
        - pattern: "IPLC-(.*?)倍"
          target: "iplc x $1"

    filter: "(?i)港|hk"       # 节点名筛选 (正则)
    exclude-filter: "美|日"   # 排除筛选
    exclude-type: "ss|http"   # 按类型排除

    payload: []               # type=inline 时直接写节点内容
```

**规则**: `override` 中可覆盖任意 proxy 通用字段; `filter` 和 `exclude-filter` 支持正则, 用 `` ` `` 分隔多个表达式。

---

## 9. Sniffer (流量嗅探)

```yaml
sniffer:
  enable: true
  force-domain: ["+"]         # 强制嗅探的域名模式, ["+"] = 全部
  skip-sni:                   # 跳过 SNI 嗅探的域名
    - www.baidu.com
    - "*.m.taobao.com"
    - "*.alicdn.com"
  sniff:
    TLS:
      ports: [443, 8443]
    HTTP:
      ports: [80, 8080-8880]
      override-destination: true   # 用嗅探到的域名覆盖连接目标
```

**规则**: 透明代理必须启用 sniffer 才能用域名规则 (否则只有 IP)。`force-domain: ["+"]` 强制所有连接都走嗅探。`override-destination: true` 在 HTTP 中会用 Host 头覆盖目标。

---

## 10. Sub Rules (子规则)

```yaml
sub-rules:
  rule1:
    - DOMAIN-SUFFIX,baidu.com,DIRECT
    - MATCH,PROXY
  sub-rule2:
    - IP-CIDR,1.1.1.1/32,REJECT
    - DOMAIN,dns.alidns.com,REJECT
```

在 rules 中引用: `SUB-RULE,(NETWORK,tcp),rule1`

---

## 11. TUN (虚拟网卡)

```yaml
listeners:
  - name: tun-in
    type: tun
    mtu: 9000
    auto-route: false         # 自动配置路由表
    auto-detect-interface: false  # 自动识别出口网卡
    strict-route: true        # 强制所有连接走 TUN
    inet4-address:            # 必填, IPv4 地址段
      - 198.19.0.1/30
    inet6-address:            # IPv6 地址段
      - "fdfe:dcba:9877::1/126"
    dns-hijack:               # 劫持的 DNS 地址
      - 0.0.0.0:53
    endpoint-independent-nat: false
    include-uid: [0]          # Linux: 仅路由这些 UID
    include-uid-range: [1000-99999]
    exclude-uid: [1000]
    exclude-uid-range: [1000-99999]
    include-android-user: [0] # Android: 仅路由这些用户
    include-package: [com.android.chrome]
    exclude-package: [com.android.captiveportallogin]
```

---

## 12. NTP (时间同步)

```yaml
ntp:
  enable: true
  write-to-system: true       # 写入系统时钟 (需 root)
  server: time.apple.com
  port: 123
  interval: 30                # 同步间隔 (分钟)
```

---

## 13. 实验性配置

```yaml
experimental:
  quic-go-disable-gso: false    # 禁用 GSO (Generic Segmentation Offload)
  quic-go-disable-ecn: false    # 禁用 ECN (Explicit Congestion Notification)
  dialer-ip4p-convert: false    # 启用 IP4P 地址转换
```

---

## 14. 透明代理模式

### 14.1 REDIRECT 模式 (仅 TCP)

```yaml
redir-port: 7892
routing-mark: 255
dns:
  listen: 0.0.0.0:1053
```

iptables 规则:
```bash
# 创建链
iptables -t nat -N MIMO_REDIR

# 防回环 (Mihomo 自身流量带 mark 255)
iptables -t nat -A MIMO_REDIR -m mark --mark 255 -j RETURN

# 端口绕过 (SSH/Console/Listeners)
iptables -t nat -A MIMO_REDIR -p tcp -m multiport --dports 22,2000 -j RETURN

# 私有 IP 直连
iptables -t nat -A MIMO_REDIR -d 127.0.0.0/8 -j RETURN
iptables -t nat -A MIMO_REDIR -d 10.0.0.0/8 -j RETURN
iptables -t nat -A MIMO_REDIR -d 192.168.0.0/16 -j RETURN

# DNS 劫持 → 1053
iptables -t nat -A MIMO_REDIR -p tcp --dport 53 -j REDIRECT --to-ports 1053
iptables -t nat -A MIMO_REDIR -p udp --dport 53 -j REDIRECT --to-ports 1053

# TCP 全部劫持 → 7892
iptables -t nat -A MIMO_REDIR -p tcp -j REDIRECT --to-ports 7892

# 挂载到 OUTPUT (本机流量)
iptables -t nat -I OUTPUT -p tcp -j MIMO_REDIR
iptables -t nat -I OUTPUT -p udp --dport 53 -j MIMO_REDIR

# 挂载到 PREROUTING (其他设备流量)
iptables -t nat -I PREROUTING -p tcp -j MIMO_REDIR
iptables -t nat -I PREROUTING -p udp --dport 53 -j MIMO_REDIR
```

### 14.2 TPROXY 模式 (TCP + UDP)

```yaml
tproxy-port: 7893
routing-mark: 255
dns:
  listen: 0.0.0.0:1053
```

使用 `iptables -t mangle -j TPROXY` 代替 REDIRECT, 支持 UDP 透明代理。

---

## 15. 分流策略

### 15.1 黑名单模式 (gfwlist)

```
gfw 列表 → 代理
cn 域名 → 直连
MATCH → 直连 (默认直连)
```

**场景**: 路由器/旁路由, 国内用户主要访问国内网站。

### 15.2 白名单模式 (大陆白名单)

```
私有 IP → 直连
cn 域名 → 直连
cn IP → 直连
MATCH → 代理 (默认代理)
```

**场景**: VPS 透明代理, 主要访问海外网站, 国内网站走直连更快。

### 15.3 DNS 分流

```
方案 A (respect-rules: true):
  - 代理规则域名 → proxy-server-nameserver (海外 DNS, 无污染)
  - cn 域名 → nameserver-policy → 国内 DNS (阿里/腾讯 DoH)
  - MATCH → 代理 → proxy-server-nameserver

方案 B (fallback 防污染):
  - nameserver → 国内 DNS (快速)
  - fallback → 海外 DNS (可信)
  - fallback-filter 判断是否污染: 国内 IP = 可信, 国外 IP = 用 fallback
```

**规则**: `respect-rules: true` 时强烈建议配置 `proxy-server-nameserver`, 否则代理规则匹配的 DNS 查询走默认 nameserver 可能绕不过 GFW。不要与 `prefer-h3` 同时使用。

---

## 16. 配置文件入口 (SS/VMess/TUIC URL)

```yaml
# 直接写 URL 作为入站
ss-config: ss://2022-blake3-aes-256-gcm:password@:23456
vmess-config: vmess://1:uuid@:12345

# TUIC 服务端入口
tuic-server:
  enable: true
  listen: 127.0.0.1:10443
  token: [TOKEN]
  certificate: ./server.crt
  private-key: ./server.key
  congestion-controller: bbr
  alpn: [h3]
```

**规则**: 这些入口的传入流量和 socks/mixed 一样按 `mode` 方式匹配处理。
