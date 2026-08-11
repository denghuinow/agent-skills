---
name: oci-cloudflare-ip-rotate
description: Rotate the Oracle Cloud Infrastructure ephemeral public IP currently referenced by a Cloudflare A record, then synchronize that DNS record to the replacement IP. Use when the user asks to change, rotate, replace, refresh, or reallocate the temporary/public IP for an OCI host identified by domain name, especially when DNS is managed in Cloudflare.
---

# OCI + Cloudflare Ephemeral IP Rotation

Use `scripts/rotate_ip.py` for all mutations. Do not manually compose destructive OCI commands when the script can perform the workflow.

## What this skill does

Given a hostname such as `host.example.com`:

1. Read the exact Cloudflare `A` record.
2. Use its current IPv4 address to find the OCI `PublicIp` in the configured tenancy/region.
3. Refuse to continue unless the OCI IP lifetime is `EPHEMERAL` and it is assigned to a primary private IP.
4. Delete the old ephemeral public IP.
5. Allocate a replacement ephemeral public IP on the same primary private IP.
6. Optionally repeat allocation until CIDR acceptance/rejection rules match.
7. Optionally perform a TCP health check against the replacement IP.
8. PATCH only the Cloudflare record `content`, preserving the record's other properties such as `proxied`, TTL, comments, tags, and settings.
9. Re-read the Cloudflare record and verify the new address.

The hostname is the resource selector. No instance OCID mapping file is required.

## Safety rules

- Always run `--dry-run` first unless the user explicitly asks to skip validation.
- Never rotate an OCI `RESERVED` public IP.
- Never delete/recreate the Cloudflare DNS record; PATCH the existing record.
- Never print, persist, commit, or request the value of `CLOUDFLARE_API_TOKEN`.
- Treat IP rotation as destructive: the released ephemeral IP is not recoverable.
- If Cloudflare update fails after OCI rotation, clearly report the replacement IP and explain that DNS still needs to be changed to it.
- When CIDR filters fail after `--max-attempts`, the script intentionally updates DNS to the final allocated IP to avoid pointing at the released address. Exit code `3` indicates criteria-not-met with DNS synchronized.

## Prerequisites

Python 3.10+ and:

```bash
python -m pip install -r requirements.txt
```

OCI authentication:

```text
~/.oci/config
```

Cloudflare API token:

```bash
export CLOUDFLARE_API_TOKEN='...'
```

The Cloudflare token should have only the zones/resources required for this task and DNS read/write access.

## Standard workflow

First validate:

```bash
python scripts/rotate_ip.py host.example.com --dry-run
```

Then rotate:

```bash
python scripts/rotate_ip.py host.example.com
```

For machine-readable output:

```bash
python scripts/rotate_ip.py host.example.com --json
```

## Region/profile selection

Use a non-default OCI profile:

```bash
python scripts/rotate_ip.py host.example.com --oci-profile production
```

Override the configured OCI region:

```bash
python scripts/rotate_ip.py host.example.com --region ap-tokyo-1
```

If the Cloudflare IP cannot be found in OCI, confirm that the selected OCI profile points to the correct tenancy and region.

## CIDR filtering

Reject one or more ranges:

```bash
python scripts/rotate_ip.py host.example.com \
  --reject-cidr 129.0.0.0/8 \
  --max-attempts 5
```

Accept only specified ranges:

```bash
python scripts/rotate_ip.py host.example.com \
  --accept-cidr 150.230.0.0/16 \
  --max-attempts 8
```

Multiple `--accept-cidr` and `--reject-cidr` options may be combined.

Do not promise that OCI will allocate an address from a requested range. Allocation is controlled by OCI.

## Optional connectivity gate

If the service is expected to accept TCP before DNS is changed:

```bash
python scripts/rotate_ip.py host.example.com --check-port 22
```

Only use this when direct connectivity to the new IP is expected. Cloudflare-proxied HTTP services, firewalls, or host-based virtual hosting can make generic health checks inappropriate.

## Result interpretation

Successful output contains:

```json
{
  "ok": true,
  "domain": "host.example.com",
  "old_ip": "203.0.113.10",
  "new_ip": "198.51.100.27",
  "attempts": 1,
  "criteria_met": true,
  "cloudflare_updated": true
}
```

Exit codes:

- `0`: success.
- `1`: OCI/Cloudflare/network/validation failure.
- `2`: invalid CLI arguments.
- `3`: requested CIDR criteria were not met, but DNS was synchronized to the final live OCI IP.

## Failure recovery

If OCI rotation succeeds but Cloudflare update fails, do not rotate again automatically. Use the new IP reported by the failure context and update the existing Cloudflare A record to that IP.

Because the old OCI ephemeral IP is released, a true rollback to the old address is generally unavailable.
