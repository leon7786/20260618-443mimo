#!/bin/bash
# fail2ban 配置脚本：保护 mimo-console 2000 端口

set -e

echo "=== 安装 fail2ban ==="
apt update && apt install -y fail2ban

echo "=== 配置 jail (封禁规则) ==="
cat > /etc/fail2ban/jail.d/mimo-console.conf <<'EOF'
[mimo-console]
enabled = true
port = 2000
protocol = tcp
filter = mimo-console
backend = systemd
journalmatch = _SYSTEMD_UNIT=mimo-console.service
maxretry = 3
findtime = 600
bantime = 600
banaction = iptables-allports
EOF

echo "=== 配置 filter (日志匹配) ==="
cat > /etc/fail2ban/filter.d/mimo-console.conf <<'EOF'
[Definition]
failregex = ^\[AUTH_FAIL\] <HOST> - Authorization failed$
ignoreregex =
EOF

echo "=== 添加认证失败日志 ==="
# console.py 已自动记录 [AUTH_FAIL] 日志
systemctl restart mimo-console.service
sleep 2
echo "控制台已重启，认证失败将记录到 journalctl"

echo "=== 重启 fail2ban ==="
systemctl enable fail2ban
systemctl restart fail2ban

echo "=== 验证配置 ==="
fail2ban-client status mimo-console

echo "
✓ fail2ban 已配置

测试封禁:
  # 3 次错误密码触发封禁
  for i in {1..4}; do curl http://127.0.0.1:2000 --user admin12:wrong; done

查看封禁列表:
  fail2ban-client status mimo-console

解封 IP:
  fail2ban-client set mimo-console unbanip 1.2.3.4
"
