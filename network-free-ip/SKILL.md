---
name: network-free-ip
description: Find candidate unused IPv4 addresses in remote Layer-2 networks by selecting an appropriate SSH probe host and performing ARP discovery from that host. Use when the user asks to find free, unused, available, or unoccupied IP addresses in a subnet or address range, especially across multiple VLANs/subnets reached through different Linux or OpenWrt probe hosts.
---

# Network Free IP Finder

Use `scripts/find_free_ip.py` to discover candidate unused IPv4 addresses from a probe host that is directly connected to the target Layer-2 network.

## Semantics

Never state that an address is definitely unused solely because it did not reply to ARP.

Classify results as:

- `USED`: responded to ARP, or is present in an active DHCP lease.
- `RESERVED`: explicitly excluded, configured as gateway, network/broadcast address, or present in an OpenWrt static DHCP host reservation.
- `CANDIDATE_FREE`: did not respond during at least two ARP scan rounds and is not known to be used/reserved.
- `UNKNOWN`: probing cannot be performed reliably, including SSH failure, missing tools, or lack of verified Layer-2 adjacency.

Do not silently convert `UNKNOWN` into `CANDIDATE_FREE`.

## Safety rules

This skill is read-only by default.

Never modify interface configuration, DHCP configuration, static leases, IP assignments, routes, firewall rules, or restart network services unless the user explicitly asks for a separate mutation.

Do not automatically install packages on a probe host. If `arp-scan` and `arping` are both unavailable, report `UNKNOWN` and tell the user which package is needed.

## Requirements

Controller:

- Python 3.9+
- OpenSSH client

Remote probe:

- Linux or OpenWrt
- SSH access
- preferred: `arp-scan`
- fallback: `arping`
- a Layer-2 interface directly attached to the target subnet

## Probe configuration

Create a JSON configuration based on `examples/probes.json`.

Each probe defines:

- `name`: logical probe name
- `ssh`: OpenSSH target, for example `root@10.0.0.20` or an SSH config alias
- `interface`: Layer-2 interface used for ARP, for example `br-lan` or `eth0.20`
- `networks`: directly attached IPv4 CIDRs
- `gateway`: optional gateway address to reserve
- `exclude`: optional additional addresses that must never be offered as free candidates

A probe may serve multiple directly attached networks.

## Standard workflow

When the user asks for free addresses:

1. Parse the requested CIDR/range and desired number of candidates.
2. Match the requested range to a configured probe.
3. SSH to the probe.
4. Verify the configured interface exists.
5. Verify the target network is directly connected on that interface. A route through `via <gateway>` is not sufficient.
6. Detect `arp-scan`; fall back to `arping` when necessary.
7. Run at least two independent ARP discovery rounds.
8. On OpenWrt, additionally inspect `/tmp/dhcp.leases` and `uci show dhcp` when available.
9. Exclude the network address, broadcast address, gateway, configured exclusions, and static DHCP reservations.
10. Return `USED`, `RESERVED`, `CANDIDATE_FREE`, and `UNKNOWN` results as appropriate.

A valid directly connected route normally looks like:

```text
192.168.20.0/24 dev br-server proto kernel scope link
```

A routed path such as this is not enough for ARP occupancy detection:

```text
192.168.20.0/24 via 10.0.0.1 dev eth0
```

## Usage

Find three candidate free addresses in a range:

```bash
python3 scripts/find_free_ip.py \
  --config examples/probes.json \
  --range 192.168.20.50-192.168.20.100 \
  --count 3
```

Scan a CIDR while limiting the requested host range:

```bash
python3 scripts/find_free_ip.py \
  --config examples/probes.json \
  --cidr 192.168.20.0/24 \
  --start 192.168.20.50 \
  --end 192.168.20.100
```

Machine-readable output:

```bash
python3 scripts/find_free_ip.py \
  --config examples/probes.json \
  --range 192.168.20.50-192.168.20.100 \
  --count 3 \
  --json
```

## Agent behavior examples

User:

> 在 192.168.20.50-192.168.20.100 中找 3 个空闲 IP

Action:

- select the probe whose configured direct network contains the full requested range
- verify Layer-2 adjacency
- execute at least two ARP scan rounds
- inspect OpenWrt DHCP leases/static reservations when available
- return the first three `CANDIDATE_FREE` addresses in numeric order

User:

> 查 10.10.30.0/24 哪些 IP 没人用

Action:

- scan the usable host range
- exclude known reservations and infrastructure addresses
- clearly label results as candidate free addresses rather than guaranteed-unused addresses

## OpenWrt notes

Typical interfaces include:

```text
br-lan
br-iot
br-guest
eth0.20
eth0.30
```

Preferred package installation, if the user separately authorizes it:

```sh
opkg update
opkg install arp-scan arp-scan-database
```

The script automatically reads OpenWrt DHCP state when `uci` exists:

```sh
cat /tmp/dhcp.leases
uci show dhcp
```

## Failure handling

No matching probe:

```text
UNKNOWN: no Layer-2 probe configured for requested range
```

Target is routed rather than directly attached:

```text
UNKNOWN: target network is not verified as directly connected on the configured interface
```

No supported ARP utility:

```text
UNKNOWN: remote probe has neither arp-scan nor arping
```

Never substitute `ping` failure as proof that an address is unused.
