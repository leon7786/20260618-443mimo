# iptables / nftables 防火墙完整用法文档

> 蒸馏来源: OpenWrt Wiki + nftables.org wiki + man nft + 本机 VPS 环境(nftables v1.0.6)
>
> **两大体系对照**:
> - **OpenWrt 体系**: 通过 UCI (`/etc/config/firewall`) → fw4/fw3 解析器 → 自动生成 nftables/iptables 规则
> - **Linux 通用/VPS 体系**: 直接使用 `nft` / `iptables` 命令或脚本文件

---

## 一、基础对比

| 对比项 | OpenWrt | 通用 Linux / VPS |
|--------|---------|-------------------|
| 配置方式 | UCI `/etc/config/firewall` | `nft` 命令 / `nft -f` 脚本文件 |
| 后端 | fw4 → nftables (22.03+) / fw3 → iptables (21.02-) | nf_tables (nftables) 或 legacy iptables |
| 配置文件 | `/etc/config/firewall` | `/etc/nftables.conf` |
| 生效命令 | `service firewall reload` | `nft -f /etc/nftables.conf` |
| 管理工具 | LuCI (Web) / UCI (命令行) | `nft` 命令行 / systemd |
| 上手难度 | 低(UCI 抽象层) | 中(需直接写规则) |
| 灵活度 | 中(常用场景全覆盖) | 高(所有 nftables 特性) |
| Docker 兼容 | 路由器场景无关 | 通过 iptables-nft 兼容层 |

---

## 二、OpenWrt 体系 (UCI 配置 /etc/config/firewall)

> 适用于: 运行 OpenWrt 的路由器/AP/网关设备

### 2.1 架构

```
+------------------+       +------------+       +-------------------+
| /etc/config/fw   | ----> | fw4 / fw3  | ----> | nftables/iptables |
| (UCI 配置)        |       | (解析器)    |       | (内核 netfilter)   |
+------------------+       +------------+       +-------------------+
```

- OpenWrt 22.03+ 默认 **fw4** (nftables 后端)
- OpenWrt 21.02- 使用 **fw3** (iptables 后端)
- **推荐**: 优先用 UCI，兜底用 `/etc/firewall.user` 或 nftables snippet

### 2.2 基本管理

```
# 编辑配置文件
vi /etc/config/firewall

# 重新加载(推荐)
service firewall reload
# 或
fw4 reload

# 查看生成的实际规则
fw4 print           # fw4 原生
nft list ruleset    # 直接看 nftables
iptables -L -n -v   # fw3 兼容查看

# 备份(改前必做)
cp /etc/config/firewall /etc/config/firewall.bak

# UCI 命令行操作
uci add firewall rule
uci set firewall.@rule[-1].name='Reject VPN to LAN'
uci set firewall.@rule[-1].src='vpn'
uci set firewall.@rule[-1].dest='lan'
uci set firewall.@rule[-1].target='REJECT'
uci commit firewall
service firewall restart
```

**注意**: LuCI 页面保存会删除注释(`#` 行)！

### 2.3 配置段详解

#### 2.3.1 defaults — 全局默认策略

```
config defaults
    option  input              'ACCEPT'       # 入站默认
    option  output             'ACCEPT'       # 出站默认
    option  forward            'REJECT'       # 转发默认
    option  drop_invalid       '1'            # 丢弃无效包
    option  synflood_protect   '1'            # SYN 洪水保护
    option  synflood_rate      '25/s'
    option  synflood_burst     '50'
    option  flow_offloading    '1'            # 软件加速
    option  flow_offloading_hw '0'            # 硬件加速
    option  tcp_syncookies     '1'            # SYN cookies
    option  tcp_ecn            '0'            # 显式拥塞通知
    option  tcp_window_scaling '1'            # TCP 窗口缩放
    option  custom_chains      '1'            # 自定义链钩子
```

#### 2.3.2 zone — 区域定义

```
config zone
    option  name      'wan'
    option  network   'wan wan6'
    option  input     'REJECT'
    option  output    'ACCEPT'
    option  forward   'REJECT'
    option  masq      '1'           # NAT 伪装
    option  mtu_fix   '1'           # MSS 钳制

config zone
    option  name      'lan'
    option  network   'lan'
    option  input     'ACCEPT'
    option  output    'ACCEPT'
    option  forward   'ACCEPT'
```

**zone 选项**:
| 选项 | 说明 |
|------|------|
| `masq` | 出口 NAT |
| `masq_src` / `masq_dest` | 限制 MASQ 源/目标子网 |
| `masq6` | IPv6 NAT (fw4 only) |
| `mtu_fix` | MSS 钳制 |
| `device` | 匹配未声明的接口(如 `tun+` 匹配所有 TUN) |
| `subnet` | 匹配子网 |
| `family` | ipv4/ipv6/any |
| `log` | 日志位域(0=filter, 1=mangle) |

#### 2.3.3 forwarding — 区域间转发

```
config forwarding
    option  src   'lan'
    option  dest  'wan'

config forwarding
    option  src   'wan'
    option  dest  'lan'       # 双向需两条
```

#### 2.3.4 rule — 流量规则

```
# 放行 WAN→LAN SSH
config rule
    option  name      'Allow SSH'
    option  src       'wan'
    option  dest      'lan'
    option  proto     'tcp'
    option  dest_port '22'
    option  target    'ACCEPT'

# 封禁特定 IP 段
config rule
    option  src     'wan'
    option  dest    'lan'
    option  proto   'tcp'
    option  src_ip  '42.56.0.0/16'
    option  dest_port '25'
    option  target  'DROP'

# 家长控制: 限制设备上网时间
config rule
    option  name       'Parental Control'
    option  src        'lan'
    option  dest       'wan'
    option  src_mac    '4C:EB:42:32:0C:9E'
    option  proto      'tcp udp'
    option  start_time '21:00:00'
    option  stop_time  '09:00:00'
    option  weekdays   'Mon Tue Wed Thu Fri'
    option  target     'REJECT'
```

**src/dest 匹配逻辑**:
| src | dest | 规则匹配 |
|-----|------|---------|
| ✓ | ✓ | 转发流量 |
| ✓ | — | 入站输入(到路由器) |
| — | ✓ | 出站输出(从路由器) |
| — | — | 出站(默认) |

**rule 匹配字段**:
| 选项 | 说明 |
|------|------|
| `src_ip` | 源 IP/CIDR |
| `src_mac` | 源 MAC |
| `src_port` | 源端口 |
| `dest_ip` | 目标 IP/CIDR |
| `dest_port` | 目标端口(支持多: `80 443 465`) |
| `proto` | tcp/udp/icmp/esp/ah/all/0 |
| `icmp_type` | ICMP 类型名称 |
| `mark` | 匹配防火墙标记 |
| `ipset` | 匹配 IP 集合 |
| `start_date` / `stop_date` | 日期范围 |
| `start_time` / `stop_time` | 时间范围 |
| `weekdays` | 星期(支持 `!` 取反) |
| `monthdays` | 每月几号 |
| `limit` / `limit_burst` | 速率限制 |

**target 动作**: `ACCEPT` / `REJECT` / `DROP` / `MARK` / `NOTRACK`

#### 2.3.5 redirect — 端口转发/NAT

```
# DNAT (端口映射)
config redirect
    option  name       'Port Forward SSH'
    option  src        'wan'
    option  src_dport  '19900'
    option  dest       'lan'
    option  dest_ip    '192.168.1.100'
    option  dest_port  '22'
    option  proto      'tcp'
    option  target     'DNAT'

# SNAT (源地址转换)
config redirect
    option  name     'SNAT to specific IP'
    option  src      'lan'
    option  src_ip   '192.168.1.50'
    option  src_dip  '1.2.3.4'
    option  dest     'wan'
    option  proto    'all'
    option  target   'SNAT'
```

#### 2.3.6 ipset — IP 集合

```
config ipset
    option  name     'blocklist'
    option  family   'ipv4'
    option  match    'src_ip'
    option  storage  'hash'
    option  maxelem  '65536'
    list    entry    '1.2.3.4'
    list    entry    '5.6.7.0/24'
```

#### 2.3.7 include — 自定义规则 (fw4)

```
# nftables 片段(推荐)
config include
    option  type     'nftables'
    option  path     '/etc/my_custom.nft'
    option  position 'chain-pre'
    option  chain    'input_wan'

# Shell 脚本(兼容 fw3)
config include
    option  type            'script'
    option  path            '/etc/firewall.user'
    option  fw4_compatible  '1'
```

**插入位置**: `ruleset-pre` / `ruleset-post` / `table-pre` / `table-post` / `chain-pre` / `chain-post`

### 2.4 实战场景

```
# IPSec 透传
config rule
    option  src    'wan'
    option  dest   'lan'
    option  proto  'ah'
    option  target 'ACCEPT'
config rule
    option  src    'wan'
    option  dest   'lan'
    option  proto  'esp'
    option  target 'ACCEPT'

# OpenVPN 区域
config zone
    option  name    'vpn'
    list    network 'tun0'
    option  input   'ACCEPT'
    option  output  'ACCEPT'
    option  forward 'REJECT'
config forwarding
    option  src  'lan'
    option  dest 'vpn'

# Cloudflare 白名单
uci set firewall.cf_proxy="rule"
uci set firewall.cf_proxy.name="Allow-Cloudflare"
uci set firewall.cf_proxy.src="wan"
uci add_list firewall.cf_proxy.dest_port="80"
uci add_list firewall.cf_proxy.dest_port="443"
uci set firewall.cf_proxy.proto="tcp"
uci set firewall.cf_proxy.target="ACCEPT"
for IP in $(wget -O - https://www.cloudflare.com/ips-v4); do
    uci add_list firewall.cf_proxy.dest_ip="${IP}"
done
uci commit firewall && service firewall restart
```

---

## 三、通用 Linux / VPS 体系 (nftables)

> 适用于: 任何 Linux 服务器/VPS/云主机

### 3.1 架构

```
+------------------+       +-------------------+
| nft 命令行 / -f 脚本 | ----> | nf_tables 内核模块 |
+------------------+       +-------------------+
```

- 单一工具 `nft`，统一管理 IPv4/IPv6/arp/bridge/netdev
- 支持 `nft -f` 批量加载
- 事务性：加载失败自动回滚
- **i** 与 Docker 共存: Docker 通过 `iptables-nft` 兼容层

### 3.2 基本命令

```
# 查看规则
nft list ruleset                  # 全部
nft list table inet filter        # 指定表
nft -a list ruleset               # 显示 handle (用于删除)
nft -n -a list ruleset            # 数字+handle

# 表管理
nft add table inet filter
nft delete table inet filter
nft flush table inet filter
nft flush ruleset                 # ⚠️ 清空所有规则!(含 Docker)

# 规则管理
nft add rule inet filter input tcp dport 22 accept          # 追加
nft insert rule inet filter input tcp dport 22 accept       # 插入开头
nft replace rule inet filter input handle 3 counter accept  # 替换
nft delete rule inet filter input handle 3                  # 删除

# 脚本加载
nft -f /etc/nftables.conf         # 加载规则文件
nft -f --check rules.nft          # 语法检查(不加载)
systemctl restart nftables        # systemd 管理
```

### 3.3 核心概念

#### Family (地址族)
| family | 用途 |
|--------|------|
| `ip` | IPv4 |
| `ip6` | IPv6 |
| `inet` | **双栈推荐** (IPv4+IPv6) |
| `arp` | ARP |
| `bridge` | 网桥 |
| `netdev` | 网卡入口/出口 |

#### 链参数
```
nft add chain inet filter input \
    { type filter hook input priority 0 \; policy drop \; }
```

| 字段 | 说明 |
|------|------|
| `type` | `filter` / `nat` / `route` |
| `hook` | `prerouting`, `input`, `forward`, `output`, `postrouting` |
| `priority` | 数值(-400~300，默认0，越小越优先) |
| `policy` | `accept` (默认) / `drop` |

**Priority 标准值**:
| 值 | 名称 | 用途 |
|-----|------|------|
| -400 | CONNTRACK_DEFRAG | 分片重组 |
| -300 | RAW | NOTRACK |
| -200 | CONNTRACK | 连接跟踪 |
| -150 | MANGLE | 包修改 |
| -100 | NAT_DST | 目标 NAT |
| 0 | FILTER | **过滤(默认)** |
| 50 | SECURITY | SELinux |
| 100 | NAT_SRC | 源 NAT |
| 300 | CONNTRACK_HELPER | 连接跟踪助手 |

**Hook 数据流**:
```
         ┌─────────────┐
         │   网络入口     │
         └──────┬──────┘
                │
       prerouting (DNAT/Mangle)
                │
          ┌─────┴─────┐
          │  路由决策    │
          └─────┬─────┘
                │
     ┌──────────┴──────────┐
     │                     │
   input                forward        → postrouting (SNAT/Masq)
 (到本机)              (转发)              → 网卡出口
     │
     ▼
  本地进程
```

#### 匹配表达式

**IPv4**:
```
ip saddr      192.168.1.0/24                  # 源 IP
ip saddr      10.0.0.0-10.255.255.255        # 范围
ip daddr      8.8.8.8                        # 目标 IP
ip daddr      { 8.8.8.8, 1.1.1.1 }           # 集合
ip protocol   { tcp, udp, icmp }             # 协议
ip ttl        64                              # TTL
ip length     333-435                         # 包长度
ip frag-off & 0x1fff != 0                    # 分片
```

**IPv6**:
```
ip6 saddr     ::1                             # 源
ip6 saddr     ::/64                           # 前缀
ip6 daddr     2001:db8::/32                   # 目标
ip6 nexthdr   { tcp, udp, icmpv6 }            # 下一头部协议
ip6 hoplimit  64                              # 跳数
```

**TCP/UDP**:
```
tcp dport     22                              # 目标端口
tcp dport     { 22, 80, 443 }                 # 端口集合
tcp dport     1024-65535                      # 端口范围
tcp sport     1024                            # 源端口
tcp flags     { fin, syn, rst, psh, ack }    # 标记
tcp flags     syn / syn,ack                   # SYN 但非 SYN-ACK
tcp doff      8                               # TCP 头部长度

udp dport     53                              # 目标端口
udp sport     67                              # 源端口
```

**ICMP**:
```
icmp type     echo-request                    # ICMPv4
icmp type     echo-reply
icmp type     destination-unreachable
icmp code     3                               # Port Unreachable

icmpv6 type   echo-request                    # ICMPv6
icmpv6 type   nd-router-advert
icmpv6 type   { nd-router-solicit, nd-neighbor-solicit, nd-neighbor-advert }
```

**连接跟踪 (conntrack)**:
```
ct state      new                             # 新建
ct state      established                     # 已建立
ct state      related                         # 相关
ct state      invalid                         # 无效 -> 丢弃!
ct state      { established, related }        # 常用组合
ct mark       1                               # ct 标记
ct helper     set "ftp"                       # CT 助手
```

**Meta 匹配**:
```
meta l4proto  tcp / 6                         # 第4层协议
meta iif      eth0                            # 入站接口(索引)
meta oif      eth0                            # 出站接口(索引)
meta iifname  "eth0"                          # 入站接口名
meta oifname  "eth0"                          # 出站接口名
meta length   256                             # 包长度
meta mark     0x1                             # skb mark
meta pkttype  broadcast / multicast           # 包类型
meta nfproto  ipv4 / ipv6                     # netfilter 协议族
meta hour     09:00-18:00                     # 小时范围(按UTC)
meta day      { 1..5 }                        # 周几(Monday=1..Sunday=7)
```

#### 动作语句

**裁决**:
```
accept                          # 放行
drop                            # 丢弃
reject                          # 拒绝
reject with icmp type port-unreachable  # 自定义
reject with icmpv6 type admin-prohibited
reject with tcp reset           # TCP RST
queue                           # 发往用户态
continue                        # 继续
return                          # 返回上级链
jump my_chain                   # 跳转(会返回)
goto my_chain                   # 跳转(不返回)
```

**NAT**:
```
# SNAT
snat to 192.168.1.1
snat to 192.168.1.1:10000-20000
masquerade                      # 动态SNAT(拨号场景)
masquerade to :1024-65535

# DNAT
dnat to 192.168.1.100
dnat to 192.168.1.100:22
redirect to 3128                # 本机重定向
```

**其他**:
```
log                             # 记录日志
log prefix "DROP: " level warn   # 自定义日志
counter                         # 计数
limit rate 10/second            # 限速
limit rate 1000/hour burst 10   # 限速+峰值
meta mark set 0x1               # 设置包标记
ct mark set 0x1                 # 设置连接标记
dup to 192.168.1.1              # 包复制(镜像)
notrack                         # 跳过连接跟踪
```

### 3.4 集合 (Sets) 与映射 (Maps)

#### 命名集合
```
table inet filter {
    set whitelist {
        type ipv4_addr
        flags interval
        elements = {
            192.168.1.0/24,
            10.0.0.1,
            172.16.0.0-172.31.255.255
        }
        timeout 1h               # 自动过期
    }

    chain forward {
        ip saddr @whitelist accept
    }
}
```

**命令行操作**:
```
nft add element    inet filter whitelist { 8.8.8.8 }
nft delete element inet filter whitelist { 8.8.8.8 }
```

**集合类型**:
| type | 说明 |
|------|------|
| `ipv4_addr` | IPv4 |
| `ipv6_addr` | IPv6 |
| `inet_service` | 端口 |
| `ether_addr` | MAC |
| `ifname` | 接口名 |
| `mark` | skb mark |

**Flags**: `interval`(范围), `timeout`(过期), `dynamic`(动态), `constant`(只读)

#### Verdict Maps (裁决映射)
```
# 内联
tcp dport vmap { 22:accept, 80:accept, 443:accept }

# 命名
table inet filter {
    map port_map {
        type inet_service : verdict
        elements = {
            22 : accept,
            80 : accept,
            443 : accept
        }
    }
    chain input { tcp dport vmap @port_map }
}
```

#### 动态集合 (限速/防攻击)
```
table inet filter {
    set flood_detect {
        type ipv4_addr
        flags dynamic,timeout
        timeout 10s
    }
    chain input {
        # 每秒 SYN 超过50次的IP加入黑名单10秒
        tcp flags syn / syn,ack \
            add @flood_detect { ip saddr limit rate 50/second } accept
        ip saddr @flood_detect drop
    }
}
```

### 3.5 状态对象

```
# 配额
quota my_quota { until 100 mbytes }
ip saddr 10.0.0.1 quota my_quota drop

# 计数器
counter http_traffic {}
tcp dport 80 name http_traffic

# CT 助手
ct helper ftp { type "ftp" protocol tcp l3proto inet }
ct helper set "ftp"
```

### 3.6 调试

```
nft -a list ruleset              # 查看 handle
nft monitor                      # 实时变更监控
nft monitor trace                # 包路径追踪
conntrack -L                     # 查看连接跟踪表
conntrack -S                     # 跟踪统计

# Trace: 追踪特定包的路径
nft add rule inet filter input ip saddr 8.8.8.8 meta nftrace set 1
nft monitor trace                # 另一个终端
# 然后触发流量
```

### 3.7 VPS 实战示例

#### 基础防火墙 (SSH + Web + Docker 共存)
```
table inet filter {
    chain input {
        type filter hook input priority 0; policy drop;

        ct state { established, related } accept
        iifname "lo" accept
        iifname "docker0" accept               # 允许 Docker 内部

        tcp dport 22 ip saddr { 你的IP/32 } accept
        tcp dport { 80, 443 } accept
        icmp type echo-request limit rate 5/second accept
        icmpv6 type echo-request limit rate 5/second accept

        log prefix "INPUT DROP: " drop
    }

    chain forward {
        type filter hook forward priority 0; policy drop;
        ct state { established, related } accept
        iifname "docker0" oifname "docker0" accept
    }

    chain output {
        type filter hook output priority 0; policy accept;
    }
}
```

#### NAT 端口转发
```
table ip nat {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        tcp dport 8080 dnat to 192.168.1.100:80
    }

    chain postrouting {
        type nat hook postrouting priority srcnat; policy accept;
        oifname "eth0" masquerade
    }
}
```

#### 透明代理 (TProxy)
```
table ip mangle {
    chain prerouting {
        type filter hook prerouting priority mangle; policy accept;
        meta mark set 0x1 meta nfproto ipv4
    }
    chain output {
        type route hook output priority mangle; policy accept;
        meta mark set 0x1 meta nfproto ipv4
    }
}

table ip nat {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        meta mark 0x1 tproxy ip to 127.0.0.1:12345
    }
}
```

---

## 四、iptables → nftables 对照 (手动规则)

| iptables / ip6tables | nftables 等价 |
|----------|---------|
| `iptables -A INPUT -p tcp --dport 22 -j ACCEPT` | `nft add rule inet filter input tcp dport 22 accept` |
| `iptables -P INPUT DROP` | `chain input { policy drop; }` |
| `iptables -N mychain` | `nft add chain inet filter mychain` |
| `iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT` | `ct state { established, related } accept` |
| `iptables -A INPUT -s 10.0.0.0/8 -j DROP` | `ip saddr 10.0.0.0/8 drop` |
| `iptables -t nat -A PREROUTING -p tcp --dport 80 -j DNAT --to 192.168.1.100:8080` | `tcp dport 80 dnat to 192.168.1.100:8080` |
| `iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE` | `oifname "eth0" masquerade` |
| `iptables -A INPUT -m limit --limit 10/s -j ACCEPT` | `limit rate 10/second accept` |
| `iptables -A INPUT -m mac --mac-source 00:11:22:33:44:55 -j DROP` | `ether saddr 00:11:22:33:44:55 drop` |
| `iptables -j LOG --log-prefix "DROP: "` | `log prefix "DROP: "` |
| `ipset create whitelist hash:ip` + `iptables -m set --match-set whitelist src -j ACCEPT` | `ip saddr @whitelist accept` |
| `iptables -A FORWARD -o eth0 -p tcp --dport 80 -j ACCEPT` | `meta oifname "eth0" tcp dport 80 accept` |

---

## 五、OpenWrt ↔ VPS 对比总结

| 功能 | OpenWrt 做法 | VPS 做法 |
|------|-------------|----------|
| 默认丢弃入站 | `option input 'REJECT'` in defaults | `chain input { policy drop; }` |
| 放行 SSH | `config rule ... src 'wan' dest_port 22 target ACCEPT` | `tcp dport 22 accept` |
| NAT (Masquerade) | `option masq '1'` in zone | `oifname "eth0" masquerade` |
| 端口转发 | `config redirect ... target DNAT` | `tcp dport 8080 dnat to ...` |
| 已连接放行 | 自动(conntrack) | `ct state established,related accept` |
| IP 集合 | `config ipset ... list entry` | `set xxx { type ipv4_addr; elements = { ... } }` |
| 自定义规则 | `config include type nftables` | 直接在链中写规则 |
| 日志 | `option log '1'` in zone | `log prefix "..."` |
| 限速 | `option limit '10/sec'` in rule | `limit rate 10/second` |
| 规则生效 | `service firewall reload` | `nft -f /etc/nftables.conf` |
| 规则查看 | `fw4 print` | `nft list ruleset` |

---

## 六、通用注意事项

1. **规则顺序决定一切**: 首次匹配即生效，之后规则不检查
2. **备份先于修改**: `cp /etc/config/firewall /etc/config/firewall.bak` (OpenWrt) 或 `nft list ruleset > /etc/nftables.conf.bak` (VPS)
3. **Docker 共存**: Docker 通过 `iptables-nft` 管理 `ip nat` 和 `ip filter` 表，标记为 `do not touch!`；在 `inet filter` 中添加自定义规则，或在 `DOCKER-USER` 链中加规则
4. **`flush ruleset` 摧毁一切**: 会清空包括 Docker 在内的所有规则，需重启 Docker 恢复
5. **优先用 UCI / inet family**: OpenWrt 优先用 UCI 配置；VPS 优先用 `inet` 族(双栈一次配置)
6. **事务性加载**: `nft -f` 是原子的——要么全生效，要么全回滚
7. **OpenWrt 11字符限制**: zone name 最长 11 个字符
8. **LuCI 删除注释**: LuCI 保存时会删掉 `#` 注释行
9. **紧急恢复**: 规则弄错导致断连 → 进 failsafe(OpenWrt) 或通过 IPMI/VNC 恢复(VPS)
