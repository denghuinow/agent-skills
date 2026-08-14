# network-free-ip

通过 SSH 选择位于目标二层网络中的 Linux/OpenWrt Probe，使用 ARP 探测指定 IPv4 网段或地址范围，找出候选空闲 IP。

## 特点

- 支持多个网段映射到不同 SSH Probe 主机
- 支持 CIDR 或起止 IP 范围
- 自动验证目标网段是否为 Probe 的二层直连网络
- 优先使用 `arp-scan`，缺失时回退 `arping`
- 至少执行两轮 ARP 探测
- OpenWrt 上自动结合 `/tmp/dhcp.leases` 和 `uci show dhcp`
- 自动排除网关、网络地址、广播地址和显式保留地址
- 输出 `USED`、`RESERVED`、`CANDIDATE_FREE`
- 默认只读，不修改网络配置

## 目录

```text
network-free-ip/
├── SKILL.md
├── README.md
├── examples/
│   └── probes.json
└── scripts/
    └── find_free_ip.py
```

## 配置 Probe

复制并修改：

```bash
cp examples/probes.json probes.json
```

示例：

```json
{
  "probes": [
    {
      "name": "server-vlan20",
      "ssh": "root@10.0.0.20",
      "interface": "br-server",
      "networks": ["192.168.20.0/24"],
      "gateway": "192.168.20.1",
      "exclude": ["192.168.20.2", "192.168.20.10"]
    }
  ]
}
```

建议优先把 `ssh` 配置成 `~/.ssh/config` 中的 Host alias，这样端口、密钥、跳板机等细节都由 OpenSSH 管理。

## 使用

在 `192.168.20.50-192.168.20.100` 中找 3 个候选空闲地址：

```bash
python3 scripts/find_free_ip.py \
  --config probes.json \
  --range 192.168.20.50-192.168.20.100 \
  --count 3
```

扫描 CIDR 中的一部分：

```bash
python3 scripts/find_free_ip.py \
  --config probes.json \
  --cidr 192.168.20.0/24 \
  --start 192.168.20.50 \
  --end 192.168.20.100
```

JSON 输出：

```bash
python3 scripts/find_free_ip.py \
  --config probes.json \
  --range 192.168.20.50-192.168.20.100 \
  --count 3 \
  --json
```

## OpenWrt Probe

推荐安装：

```sh
opkg update
opkg install arp-scan arp-scan-database
```

脚本不会自动安装软件包。

如果没有 `arp-scan`，但系统提供 `arping`，会自动回退到逐 IP 探测。

## 为什么必须二层直连

ARP 不跨三层路由器。因此 Probe 必须在目标子网所在的二层广播域中。

允许：

```text
192.168.20.0/24 dev br-server proto kernel scope link
```

不允许把下面这种路由当成可执行 ARP 探测：

```text
192.168.20.0/24 via 10.0.0.1 dev eth0
```

## 关于“空闲”的定义

`CANDIDATE_FREE` 只表示：

1. 多轮 ARP 探测没有收到响应；
2. 未出现在当前 DHCP lease 中；
3. 未命中 OpenWrt 静态 DHCP reservation；
4. 未被配置为保留地址。

它不能发现当前关机、但手工配置了静态 IP 的设备，因此不应表述为“100% 未使用”。
