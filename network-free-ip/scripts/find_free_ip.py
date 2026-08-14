#!/usr/bin/env python3

import argparse
import ipaddress
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class Probe:
    name: str
    ssh: str
    interface: str
    networks: List[ipaddress.IPv4Network]
    gateway: Optional[ipaddress.IPv4Address]
    exclude: Set[ipaddress.IPv4Address]


def run_local(cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def ssh_run(target: str, command: str, timeout: int = 30) -> Tuple[int, str, str]:
    proc = run_local(
        [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=8",
            target,
            command,
        ],
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def load_probes(path: str) -> List[Probe]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    probes = []
    for item in data.get("probes", []):
        networks = [ipaddress.ip_network(x, strict=False) for x in item["networks"]]
        gateway = ipaddress.ip_address(item["gateway"]) if item.get("gateway") else None
        exclude = {ipaddress.ip_address(x) for x in item.get("exclude", [])}
        if gateway:
            exclude.add(gateway)
        probes.append(
            Probe(
                name=item["name"],
                ssh=item["ssh"],
                interface=item["interface"],
                networks=networks,
                gateway=gateway,
                exclude=exclude,
            )
        )
    return probes


def determine_range(args):
    if args.range:
        try:
            a, b = args.range.split("-", 1)
            start = ipaddress.ip_address(a.strip())
            end = ipaddress.ip_address(b.strip())
        except Exception as exc:
            raise RuntimeError(f"invalid range: {args.range}") from exc
    else:
        if not args.cidr:
            raise RuntimeError("either --range or --cidr is required")
        network = ipaddress.ip_network(args.cidr, strict=False)
        if network.version != 4:
            raise RuntimeError("IPv4 only")
        start = ipaddress.ip_address(args.start) if args.start else network.network_address + 1
        end = ipaddress.ip_address(args.end) if args.end else network.broadcast_address - 1
        if start not in network or end not in network:
            raise RuntimeError("start/end must be inside CIDR")

    if start.version != 4 or end.version != 4:
        raise RuntimeError("IPv4 only")
    if int(start) > int(end):
        raise RuntimeError("range start is greater than end")
    return start, end


def choose_probe(probes, start, end):
    matches = []
    for probe in probes:
        for network in probe.networks:
            if start in network and end in network:
                matches.append((probe, network))
    if not matches:
        raise RuntimeError(f"no Layer-2 probe configured for range {start}-{end}")
    matches.sort(key=lambda x: x[1].prefixlen, reverse=True)
    return matches[0]


def validate_l2(probe: Probe, network: ipaddress.IPv4Network) -> None:
    iface = shlex.quote(probe.interface)
    rc, out, err = ssh_run(
        probe.ssh,
        f"ip link show dev {iface} >/dev/null 2>&1 && ip -4 route show",
    )
    if rc != 0:
        raise RuntimeError(f"unable to verify interface {probe.interface}: {err.strip()}")

    found = False
    for line in out.splitlines():
        if str(network) not in line:
            continue
        if re.search(rf"\bdev\s+{re.escape(probe.interface)}\b", line) and " via " not in f" {line} ":
            found = True
            break
    if not found:
        raise RuntimeError(
            f"{network} is not verified as directly connected through {probe.interface}"
        )


def detect_tool(probe: Probe) -> str:
    rc, out, _ = ssh_run(
        probe.ssh,
        "if command -v arp-scan >/dev/null 2>&1; then echo arp-scan; "
        "elif command -v arping >/dev/null 2>&1; then echo arping; else echo none; fi",
    )
    if rc != 0:
        raise RuntimeError("unable to detect ARP tools")
    return out.strip().splitlines()[-1]


def parse_arp_scan(text: str) -> Dict[ipaddress.IPv4Address, str]:
    found = {}
    pattern = re.compile(
        r"^(?P<ip>\d+\.\d+\.\d+\.\d+)\s+"
        r"(?P<mac>[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b"
    )
    for line in text.splitlines():
        m = pattern.match(line.strip())
        if m:
            found[ipaddress.ip_address(m.group("ip"))] = m.group("mac").lower()
    return found


def arp_scan_round(probe, start, end, retry, timeout_ms):
    iface = shlex.quote(probe.interface)
    target_range = shlex.quote(f"{start}-{end}")
    cmd = (
        f"arp-scan --interface={iface} --retry={int(retry)} "
        f"--timeout={int(timeout_ms)} {target_range} 2>/dev/null || true"
    )
    _, out, _ = ssh_run(probe.ssh, cmd, timeout=120)
    return parse_arp_scan(out)


def arping_one(probe, ip, retry, timeout_sec):
    iface = shlex.quote(probe.interface)
    ipq = shlex.quote(str(ip))
    cmd = f"arping -I {iface} -c {int(retry)} -w {int(timeout_sec)} {ipq} >/dev/null 2>&1"
    rc, _, _ = ssh_run(probe.ssh, cmd, timeout=max(10, timeout_sec + 5))
    return rc == 0


def read_openwrt_state(probe):
    leased = set()
    reserved = set()
    rc, out, _ = ssh_run(
        probe.ssh,
        "if command -v uci >/dev/null 2>&1; then "
        "echo __OPENWRT__; cat /tmp/dhcp.leases 2>/dev/null || true; "
        "echo __UCI__; uci show dhcp 2>/dev/null || true; fi",
    )
    if rc != 0 or "__OPENWRT__" not in out:
        return leased, reserved

    lease_part = out.split("__OPENWRT__", 1)[1].split("__UCI__", 1)[0]
    uci_part = out.split("__UCI__", 1)[1]

    for line in lease_part.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                leased.add(ipaddress.ip_address(parts[2]))
            except ValueError:
                pass

    for match in re.finditer(r"\.ip='(\d+\.\d+\.\d+\.\d+)'", uci_part):
        try:
            reserved.add(ipaddress.ip_address(match.group(1)))
        except ValueError:
            pass

    return leased, reserved


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--cidr")
    p.add_argument("--range")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--count", type=int, default=0)
    p.add_argument("--rounds", type=int, default=2)
    p.add_argument("--retry", type=int, default=3)
    p.add_argument("--timeout-ms", type=int, default=500)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.rounds < 2:
        raise RuntimeError("--rounds must be at least 2")

    start, end = determine_range(args)
    probe, network = choose_probe(load_probes(args.config), start, end)
    validate_l2(probe, network)
    tool = detect_tool(probe)
    if tool == "none":
        raise RuntimeError("remote probe has neither arp-scan nor arping")

    all_ips = [ipaddress.ip_address(i) for i in range(int(start), int(end) + 1)]
    excluded = set(probe.exclude)
    excluded.add(network.network_address)
    excluded.add(network.broadcast_address)

    dhcp_leased, dhcp_reserved = read_openwrt_state(probe)
    excluded |= dhcp_reserved
    used: Dict[ipaddress.IPv4Address, str] = {}

    if tool == "arp-scan":
        for _ in range(args.rounds):
            used.update(arp_scan_round(probe, start, end, args.retry, args.timeout_ms))
    else:
        timeout_sec = max(1, int((args.timeout_ms / 1000.0) * args.retry) + 1)
        for ip in all_ips:
            if ip in excluded:
                continue
            for _ in range(args.rounds):
                if arping_one(probe, ip, args.retry, timeout_sec):
                    used[ip] = "arp-response"
                    break

    for ip in dhcp_leased:
        if start <= ip <= end and ip not in used:
            used[ip] = "dhcp-lease"

    candidate_free = [ip for ip in all_ips if ip not in excluded and ip not in used]
    if args.count > 0:
        candidate_free = candidate_free[:args.count]

    result = {
        "probe": probe.name,
        "ssh": probe.ssh,
        "interface": probe.interface,
        "network": str(network),
        "range": f"{start}-{end}",
        "tool": tool,
        "rounds": args.rounds,
        "candidate_free": [str(x) for x in candidate_free],
        "used": [
            {"ip": str(ip), "mac_or_source": value}
            for ip, value in sorted(used.items(), key=lambda x: int(x[0]))
            if start <= ip <= end
        ],
        "reserved": [
            str(x) for x in sorted(excluded, key=int) if start <= x <= end
        ],
        "warning": (
            "CANDIDATE_FREE means no ARP response was observed during multiple scans "
            "and no known reservation was found. It is not proof that the address has "
            "never been statically assigned to an offline device."
        ),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"Probe:     {probe.name}")
    print(f"SSH:       {probe.ssh}")
    print(f"Interface: {probe.interface}")
    print(f"Network:   {network}")
    print(f"Range:     {start}-{end}")
    print(f"Tool:      {tool}")
    print(f"Rounds:    {args.rounds}\n")

    print("CANDIDATE_FREE")
    for ip in candidate_free:
        print(ip)

    print("\nUSED")
    for ip, value in sorted(used.items(), key=lambda x: int(x[0])):
        if start <= ip <= end:
            print(f"{str(ip):<15} {value}")

    print("\nRESERVED")
    for ip in sorted(excluded, key=int):
        if start <= ip <= end:
            print(ip)

    print("\nWARNING: candidate addresses are not guaranteed unused; offline statically configured devices cannot always be detected.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"UNKNOWN: {exc}", file=sys.stderr)
        sys.exit(2)
