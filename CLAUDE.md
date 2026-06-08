# Mihomo VPS 透明代理项目

## 项目概述

本机运行 Mihomo (Clash.Meta) 内核，通过 Web 控制台管理：
- **本地服务端**: VPS 作为入站节点 (SS/Hysteria2/TUIC/AnyTLS/HTTP/SOCKS5)
- **链式代理**: 入口 Inbound → 多级出站代理串联 → 互联网
- **透明代理**: iptables 劫持本机流量 → Mihomo → 国内外分流

## 路径

| 路径 | 用途 |
|------|------|
| `/root/projects/20260515-mimo443/` | 项目根目录 (APP_DIR, 由 `__file__` 推导, 可被 env 覆盖) |
| `config.yaml` | Mihomo 运行配置 (由 console.py 动态生成) |
| `mimo-linux-amd64` | Mihomo 二进制 |
| `console/console.py` | Web 控制台 (Flask-less, 纯 stdlib) |
| `console/state.yaml` | 控制台 UI 持久化状态 |
| `console/console-auth.yaml` | 控制台登录密码 |
| `start.sh` | 安装/启动/管理脚本 |
| `tproxy.sh` | 透明代理 iptables 规则脚本 |
| `ruleset/` | 规则集 .mrs 文件缓存 |
| `certs/` | TLS 证书 |

## 服务

| 服务 | 端口 | 说明 |
|------|------|------|
| `mimo.service` | 7892(tproxy), 1053(DNS), 19093(API), 2002(链式入口) | 内核 |
| `mimo-console.service` | 2000 | Web 管理界面 |
| `mimo-tproxy.service` | - | iptables 透明代理规则 |
| `mimo-healthcheck.timer` | - | 每5分钟连通性检查 |

## console.py 架构

### Web: 纯 stdlib HTTP Server
- `ThreadingHTTPServer` + `BaseHTTPRequestHandler`
- 端口: 2000
- 认证: HTTP Basic Auth (PBKDF2-SHA256)
- HTML 内嵌在 `HTML = r"""..."""` 字符串中
- 前端: 原生 JS, 无框架

### API endpoints (POST, JSON)

| 路径 | 功能 |
|------|------|
| `/api/state` | 读取当前状态 |
| `/api/save-state` | 保存 UI 状态 (不触发重载) |
| `/api/parse/local-services` | YAML → listener 卡片 |
| `/api/parse/chain` | YAML → 链式节点 |
| `/api/apply` | **核心**: 渲染 config.yaml, 验证, 写入, 热加载, 连通性测试 |
| `/api/performance` | 修改性能设置(含分流/tproxy 开关), 校验+保存+重载 |
| `/api/validate` | 仅校验不应用 |
| `/api/connectivity-test` | 仅测试连通性 |
| `/api/local-node` | 复制节点 YAML |
| `/api/local-node-url` | 复制节点 URL |

### 配置生成流程 (`/api/apply`)

```
state.yaml (UI 状态) + config.yaml (现有配置)
        ↓
  render_config(existing, state)
        ↓
  1. apply_performance_to_config()  → 写入基础配置 + DNS + tproxy
  2. without_managed()              → 清理旧的管理对象
  3. build_managed_objects()        → 从 state 生成 listeners + proxies
  4. apply_split_rules()            → 写入规则集 + 路由 + sniffer
        ↓
  validate_config_file() → mimo -t 校验
        ↓
  save_config_in_place() → 写入 config.yaml
  save_yaml_atomic()     → 写入 state.yaml
        ↓
  recreate_mihomo() → API 热加载, 失败则 systemctl reload
  test_google_connectivity() → curl 连通性测试
```

### `/api/performance` 流程

```
state.yaml + 用户勾选 settings
        ↓
  apply_performance_to_config()  → 写入性能参数到 config
  apply_split_rules()            → 重建路由规则 (tproxy 开关影响 MATCH 目标)
  validate → save → reload
  _apply_tproxy_bypass()         → 动态写 iptables-legacy 规则
  systemctl enable/disable mimo-tproxy.service
```

### DNS 架构

```
中国大陆域名 (白名单模式, rule-set:cn_domain):
  直连 → nameserver-policy → https://dns.alidns.com/dns-query (阿里 DoH)

非中国大陆域名 (MATCH):
  走代理 → proxy-server-nameserver → 1.1.1.1 / 8.8.8.8 (DoH)
  通过链式代理隧道出去, 无 DNS 污染

兜底 → nameserver → 阿里/腾讯 DoH; bootstrap → default-nameserver (180.76.76.76)

关键: respect-rules: true → DNS 查询遵循路由规则选择上游
全局代理模式 (分流关): 移除 nameserver-policy, 全部经隧道解析
注: 已删 fallback-filter{geoip:CN} → 不再加载 Country.mmdb
```

### 分流规则 (两态, 与透明代理解耦)

```yaml
分流开 (大陆白名单, 3 个规则文件):
 1. IP 私有/保留地址 → DIRECT (no-resolve); 198.18.0.0/16 → REJECT
 2. RULE-SET,private   → DIRECT          # 私有域名
 3. RULE-SET,cn_domain → DIRECT          # 中国域名白名单
 4. RULE-SET,cn_ip     → DIRECT (no-resolve)  # 中国 IP 白名单
 5. MATCH → {出口}                        # 其余全走代理

分流关 (全局代理, 0 规则文件):
 1. IP 私有/保留地址 → DIRECT/REJECT
 2. MATCH → {出口}                        # 除内网外全走代理

{出口} = 链式 exit_proxy (链式启用且有出口) 否则 节点选择 group
核心: 白名单中国内容其余走代理; 透明代理开关不影响路由规则
```

### 透明代理机制

```
本机出站 TCP → iptables REDIRECT → 127.0.0.1:7892
DNS 查询 UDP:53 → iptables REDIRECT → 127.0.0.1:1053

iptables MIMO_REDIR 链:
  - mark 255 → RETURN (Mihomo 自身流量不劫持)
  - dport 在绕过列表 → RETURN (SSH/Console/Listener 端口)
  - 私有 IP → RETURN
  - dport 53 → REDIRECT 1053
  - TCP → REDIRECT 7892

绕过端口动态收集:
  - config 中所有 listener 的 port
  - DNS listen port
  - external-controller port
  - redir-port
  - Console port (2000)
  - SSH 端口 (从 ss -lntp 检测)
```

### 链式代理机制

```
state.chain = {
  enabled: true/false,
  entry: {type: http, port: 2002, listen: 0.0.0.0, users: [...]},
  nodes: [{type: ss, server: IP, port: PORT, cipher: ..., password: ...}],
  exit_proxy: "node-name"
}

build_managed_objects():
  - 链式 entry → 变成 listener (接受连接)
  - 链式 nodes → 变成 proxies (出站), 通过 dialer-proxy 串联
  - split_route=true 时 entry 不设 proxy 字段 (走路由规则)
  - split_route=false 时 entry.proxy = nodes[-1].name (直连出口)

MATCH 目标 (与 tproxy 解耦):
  - 链式启用且有 exit_proxy → MATCH 指向 chain.exit_proxy
  - 否则 → MATCH 指向 节点选择 (select 组)
  - 分流开(白名单)/分流关(全局) 均如此; tproxy 开关不影响路由
```

### 性能设置 (performance)

```python
{
    "keep_alive": bool,       # 长连接
    "tcp_concurrent": bool,   # TCP 并发
    "unified_delay": bool,    # 统一延迟
    "fake_ip": False,         # 强制 redir-host, 不使用 fake-ip
    "split_route": bool,      # 国内外分流 (默认 true)
    "ipv6": bool,             # IPv6 (默认 false)
    "tproxy": bool,           # VPS 透明代理
    "connection_timeout": 3|5|10,  # 超时秒数
    "log_level": "info|warning|error|debug",
}
```

## 关键函数速查

| 函数 | 作用 |
|------|------|
| `render_config(existing, state)` | 核心: 合并生成最终 config |
| `build_managed_objects(state)` | state → listeners + proxies |
| `apply_performance_to_config(config, settings)` | 写入性能+DNS+tproxy |
| `apply_split_rules(config, proxy_names, match_target, split_route)` | 写入规则集+路由+sniffer (split_route 二分: 白名单/全局) |
| `split_rules(t)` / `global_rules(t)` | 白名单规则 / 全局代理规则 (共用 `RESERVED_IP_RULES`) |
| `apply_performance_settings(settings)` | 性能变更入口 (含 tproxy) |
| `apply_state(state)` | 完整 apply 入口 |
| `_apply_tproxy_bypass(config)` | 写 iptables-legacy 规则 |
| `_tproxy_bypass_ports(config)` | 收集需绕过的端口 |
| `recreate_mihomo()` | API 热加载, 失败则 systemctl reload |
| `test_google_connectivity(state)` | curl 连接测试 |
| `save_config_in_place()` | 原子写入 config.yaml |
| `save_yaml_atomic()` | 原子写入 state.yaml (tempfile + os.replace) |
| `load_yaml()` | 读取 YAML |

## 规则集 (rule-providers)

3 个规则集 (大陆白名单), 从 `MetaCubeX/meta-rules-dat` 下载到 `./ruleset/`:

| 名称 | behavior | 文件 | 用途 |
|------|----------|------|------|
| cn_domain | domain | `geosite/cn.mrs` | 中国域名白名单 |
| cn_ip | ipcidr | `geoip/cn.mrs` | 中国 IP 段白名单 |
| private | domain | `geosite/private.mrs` | 私有/内网域名 |

> 全局代理模式 (分流关) 不加载任何 rule-provider。
> 已移除 gfw/apple_cn/steam_cn/microsoft_cn (白名单下冗余) 及全部 geo db (GeoIP.dat/geoip.metadb/geosite.dat/Country.mmdb)。

## 修改注意事项

1. **iptables**: 必须用 `iptables-legacy`, 不能用 `iptables` (nf_tables 后端与 Docker 冲突)
2. **配置热加载**: 优先用 `PUT /configs?force=true` API, 失败回退 `systemctl reload mimo.service`
3. **端口冲突检测**: `build_managed_objects` 会自动序号递增避免端口冲突
4. **原子写入**: 配置文件和 state 都用 tempfile + os.replace 保证原子性
5. **LOCK**: 全局 `threading.Lock()` 防止并发修改 config.yaml
6. **console 重启**: 修改 console.py 后 `systemctl restart mimo-console.service`
7. **state vs config**: state.yaml 是 UI 状态 (textareas, checkboxes), config.yaml 是 Mihomo 运行配置
8. **CLAUDE_CODE_EXECPATH**: 环境变量被篡改为 bun, 已在 bashrc 中 override 为 `/root/.local/bin/claude`, grep shell 函数包装器已修复
