#!/usr/bin/env python3
"""Rotate an OCI ephemeral public IP selected by a Cloudflare A record."""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import oci
import requests
from oci.exceptions import ServiceError

CF_API = "https://api.cloudflare.com/client/v4"


class RotateError(RuntimeError):
    pass


@dataclass
class Result:
    domain: str
    zone_name: str
    zone_id: str
    record_id: str
    old_ip: str
    new_ip: str | None
    private_ip_id: str
    vnic_id: str | None
    attempts: int
    criteria_met: bool
    cloudflare_updated: bool
    dry_run: bool


class Cloudflare:
    def __init__(self, token: str, timeout: float = 20.0) -> None:
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "oci-cloudflare-ip-rotate/1.0",
        })
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        r = self.s.request(method, CF_API + path, timeout=self.timeout, **kwargs)
        try:
            data = r.json()
        except ValueError as e:
            raise RotateError(f"Cloudflare returned non-JSON HTTP {r.status_code}") from e
        if not r.ok or not data.get("success", False):
            raise RotateError(
                f"Cloudflare API failed HTTP {r.status_code}: "
                f"{json.dumps(data.get('errors', data), ensure_ascii=False)}"
            )
        return data

    def find_zone(self, fqdn: str) -> tuple[str, str]:
        labels = fqdn.rstrip(".").split(".")
        # Try every suffix from most specific to least specific. Cloudflare's
        # `name=` filter returns exact zones, so subdomain hostnames are safe.
        for i in range(0, max(1, len(labels) - 1)):
            candidate = ".".join(labels[i:])
            if candidate.count(".") < 1:
                continue
            data = self._request(
                "GET", "/zones",
                params={"name": candidate, "status": "active", "per_page": 50},
            )
            exact = [z for z in data["result"] if z["name"].rstrip(".") == candidate]
            if len(exact) == 1:
                return exact[0]["id"], exact[0]["name"]
        raise RotateError(f"No active Cloudflare zone found for {fqdn}")

    def get_a_record(self, zone_id: str, fqdn: str) -> dict[str, Any]:
        data = self._request(
            "GET",
            f"/zones/{zone_id}/dns_records",
            params={"type": "A", "name": fqdn, "per_page": 100},
        )
        records = [
            r for r in data["result"]
            if r.get("type") == "A" and r.get("name", "").rstrip(".") == fqdn.rstrip(".")
        ]
        if len(records) != 1:
            raise RotateError(
                f"Expected exactly one Cloudflare A record for {fqdn}, found {len(records)}"
            )
        return records[0]

    def patch_record_ip(self, zone_id: str, record_id: str, new_ip: str, retries: int = 3) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                # PATCH only `content`; all other existing record attributes remain unchanged.
                return self._request(
                    "PATCH",
                    f"/zones/{zone_id}/dns_records/{record_id}",
                    json={"content": new_ip},
                )["result"]
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(attempt * 2)
        raise RotateError(f"Cloudflare DNS update failed after {retries} attempts: {last_error}")


def load_oci_config(path: str, profile: str, region: str | None) -> dict[str, Any]:
    config = oci.config.from_file(path, profile)
    if region:
        config["region"] = region
    oci.config.validate_config(config)
    return config


def get_public_ip_by_address(vcn: oci.core.VirtualNetworkClient, ip: str):
    details = oci.core.models.GetPublicIpByIpAddressDetails(ip_address=ip)
    try:
        return vcn.get_public_ip_by_ip_address(details).data
    except ServiceError as e:
        if e.status == 404:
            raise RotateError(
                f"OCI public IP {ip} was not found in configured tenancy/region"
            ) from e
        raise


def assert_rotatable(vcn: oci.core.VirtualNetworkClient, public_ip):
    lifetime = str(public_ip.lifetime or "").upper()
    if lifetime != "EPHEMERAL":
        raise RotateError(
            f"OCI IP {public_ip.ip_address} is {lifetime or 'UNKNOWN'}, not EPHEMERAL"
        )
    private_ip_id = getattr(public_ip, "assigned_entity_id", None)
    if not private_ip_id:
        private_ip_id = getattr(public_ip, "private_ip_id", None)
    if not private_ip_id:
        raise RotateError("OCI public IP is not assigned to a private IP")
    private_ip = vcn.get_private_ip(private_ip_id).data
    if getattr(private_ip, "is_primary", True) is False:
        raise RotateError("Assigned private IP is not the VNIC primary private IP")
    return private_ip


def wait_deleted(vcn: oci.core.VirtualNetworkClient, public_ip_id: str, timeout: float = 45.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            vcn.get_public_ip(public_ip_id)
        except ServiceError as e:
            if e.status == 404:
                return
            raise
        time.sleep(1)
    raise RotateError(f"Timed out waiting for OCI public IP {public_ip_id} deletion")


def wait_assigned(vcn: oci.core.VirtualNetworkClient, public_ip_id: str, timeout: float = 60.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = vcn.get_public_ip(public_ip_id).data
        state = str(last.lifecycle_state or "").upper()
        if state == "ASSIGNED" and last.ip_address:
            return last
        if state in {"TERMINATED", "TERMINATING"}:
            raise RotateError(f"New OCI public IP entered unexpected state {state}")
        time.sleep(1)
    raise RotateError(
        f"Timed out waiting for new OCI public IP assignment; "
        f"last state={getattr(last, 'lifecycle_state', None)}"
    )


def create_ephemeral(vcn: oci.core.VirtualNetworkClient, private_ip):
    details = oci.core.models.CreatePublicIpDetails(
        compartment_id=private_ip.compartment_id,
        lifetime="EPHEMERAL",
        private_ip_id=private_ip.id,
        display_name="rotated-by-oci-cloudflare-ip-rotate",
    )
    created = vcn.create_public_ip(details).data
    return wait_assigned(vcn, created.id)


def parse_networks(values: list[str]):
    return [ipaddress.ip_network(value, strict=False) for value in values]


def ip_matches(ip: str, accept, reject) -> bool:
    addr = ipaddress.ip_address(ip)
    if accept and not any(addr in n for n in accept):
        return False
    if any(addr in n for n in reject):
        return False
    return True


def tcp_health(ip: str, port: int, timeout: float) -> None:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return
    except OSError as e:
        raise RotateError(f"TCP health check failed for {ip}:{port}: {e}") from e


def rotate(args: argparse.Namespace) -> Result:
    domain = args.domain.rstrip(".").lower()
    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not cf_token:
        raise RotateError("CLOUDFLARE_API_TOKEN is not set")

    cf = Cloudflare(cf_token, timeout=args.http_timeout)
    zone_id, zone_name = cf.find_zone(domain)
    record = cf.get_a_record(zone_id, domain)
    old_ip = record["content"]

    try:
        ipaddress.IPv4Address(old_ip)
    except ipaddress.AddressValueError as e:
        raise RotateError(f"Cloudflare A record content is not IPv4: {old_ip}") from e

    config = load_oci_config(args.oci_config, args.oci_profile, args.region)
    vcn = oci.core.VirtualNetworkClient(config)
    current_public = get_public_ip_by_address(vcn, old_ip)
    private_ip = assert_rotatable(vcn, current_public)
    vnic_id = getattr(private_ip, "vnic_id", None)

    accept = parse_networks(args.accept_cidr)
    reject = parse_networks(args.reject_cidr)

    if args.dry_run:
        return Result(
            domain=domain, zone_name=zone_name, zone_id=zone_id,
            record_id=record["id"], old_ip=old_ip, new_ip=None,
            private_ip_id=private_ip.id, vnic_id=vnic_id, attempts=0,
            criteria_met=False, cloudflare_updated=False, dry_run=True,
        )

    last_new = None
    criteria_met = False
    attempts = 0

    for attempts in range(1, args.max_attempts + 1):
        victim = current_public if attempts == 1 else last_new
        if victim is None:
            raise RotateError("Internal error: no OCI public IP available to rotate")

        vcn.delete_public_ip(victim.id)
        wait_deleted(vcn, victim.id, timeout=args.oci_timeout)
        last_new = create_ephemeral(vcn, private_ip)
        if ip_matches(last_new.ip_address, accept, reject):
            criteria_met = True
            break

    if last_new is None:
        raise RotateError("OCI did not return a replacement public IP")

    if args.check_port is not None:
        tcp_health(last_new.ip_address, args.check_port, args.check_timeout)

    cf.patch_record_ip(zone_id, record["id"], last_new.ip_address, retries=args.cf_retries)
    confirmed = cf.get_a_record(zone_id, domain)
    if confirmed.get("content") != last_new.ip_address:
        raise RotateError(
            f"Cloudflare verification mismatch: expected {last_new.ip_address}, "
            f"got {confirmed.get('content')}"
        )

    return Result(
        domain=domain, zone_name=zone_name, zone_id=zone_id,
        record_id=record["id"], old_ip=old_ip, new_ip=last_new.ip_address,
        private_ip_id=private_ip.id, vnic_id=vnic_id, attempts=attempts,
        criteria_met=criteria_met, cloudflare_updated=True, dry_run=False,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Rotate an OCI ephemeral public IP selected by a Cloudflare A record."
    )
    p.add_argument("domain", help="Cloudflare hostname whose A record points to the OCI IP")
    p.add_argument("--oci-config", default=str(Path.home() / ".oci" / "config"))
    p.add_argument("--oci-profile", default="DEFAULT")
    p.add_argument("--region", help="Override OCI region from the selected profile")
    p.add_argument("--max-attempts", type=int, default=1)
    p.add_argument("--accept-cidr", action="append", default=[], metavar="CIDR")
    p.add_argument("--reject-cidr", action="append", default=[], metavar="CIDR")
    p.add_argument("--check-port", type=int)
    p.add_argument("--check-timeout", type=float, default=5.0)
    p.add_argument("--http-timeout", type=float, default=20.0)
    p.add_argument("--oci-timeout", type=float, default=45.0)
    p.add_argument("--cf-retries", type=int, default=3)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def main() -> int:
    args = build_parser().parse_args()
    if args.max_attempts < 1:
        print("error: --max-attempts must be >= 1", file=sys.stderr)
        return 2
    try:
        result = rotate(args)
    except (RotateError, ServiceError, requests.RequestException, ValueError) as e:
        payload = {"ok": False, "error": str(e)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    payload = {"ok": True, **asdict(result)}
    print(json.dumps(payload, ensure_ascii=False) if args.json else json.dumps(payload, ensure_ascii=False, indent=2))

    if not result.dry_run and not result.criteria_met and (args.accept_cidr or args.reject_cidr):
        print(
            "WARNING: CIDR criteria were not met; DNS was synchronized to the final "
            "allocated IP to avoid leaving the hostname on a released address.",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
