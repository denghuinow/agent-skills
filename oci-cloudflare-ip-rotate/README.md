# OCI Cloudflare IP Rotate Skill

Agent Skill for rotating an **Oracle Cloud Infrastructure (OCI) ephemeral public IP** by hostname and then synchronizing the existing **Cloudflare A record**.

## Why

The operational object is often a hostname, not an OCI instance OCID:

```text
host.example.com
  -> Cloudflare A record
  -> current public IPv4
  -> OCI PublicIp
  -> primary PrivateIp / VNIC
  -> replacement Ephemeral PublicIp
  -> Cloudflare A record update
```

This skill implements that workflow without maintaining a separate hostname-to-instance mapping.

## Features

- Selects the OCI host from the current Cloudflare A record.
- Refuses to rotate non-ephemeral OCI public IPs.
- Reallocates on the same primary private IP.
- Updates the existing DNS record in place with Cloudflare `PATCH`.
- Preserves proxy state, TTL, comments, tags, and other record properties because only `content` is patched.
- `--dry-run` validation.
- JSON output for agent/tool integration.
- Optional accept/reject CIDR filters and bounded retries.
- Optional TCP connectivity check before DNS cutover.
- Re-reads Cloudflare after the update to verify the record.

## Install

```bash
git clone https://github.com/denghuinow/agent-skills.git
cd agent-skills/oci-cloudflare-ip-rotate
python -m pip install -r requirements.txt
```

Requirements:

- Python 3.10+
- OCI Python SDK
- `requests`
- an OCI API configuration, normally `~/.oci/config`
- a Cloudflare API token in `CLOUDFLARE_API_TOKEN`

## Cloudflare permissions

Use a scoped API token. It needs DNS read/write access to the zone(s) being managed. Avoid Global API Keys.

```bash
export CLOUDFLARE_API_TOKEN='...'
```

Do not commit this token.

## OCI permissions

The OCI principal needs enough Core Networking permission to:

- read the public IP selected by address;
- read its associated private IP;
- delete the current ephemeral public IP;
- create a new ephemeral public IP on that private IP.

Scope the policy to the smallest appropriate compartment/tenancy for your environment.

## Usage

Validate without writes:

```bash
python scripts/rotate_ip.py host.example.com --dry-run
```

Rotate and synchronize DNS:

```bash
python scripts/rotate_ip.py host.example.com
```

JSON output:

```bash
python scripts/rotate_ip.py host.example.com --json
```

Use a specific OCI profile/region:

```bash
python scripts/rotate_ip.py host.example.com \
  --oci-profile production \
  --region ap-tokyo-1
```

Reject a range and retry allocation:

```bash
python scripts/rotate_ip.py host.example.com \
  --reject-cidr 129.0.0.0/8 \
  --max-attempts 5
```

Accept only selected ranges:

```bash
python scripts/rotate_ip.py host.example.com \
  --accept-cidr 150.230.0.0/16 \
  --max-attempts 8
```

Require SSH reachability before DNS cutover:

```bash
python scripts/rotate_ip.py host.example.com --check-port 22
```

## Important behavior

OCI ephemeral IP rotation is destructive. Once the old address is deleted, it is returned to OCI's address pool and should not be treated as recoverable.

If CIDR filters are specified but no allocated address matches within `--max-attempts`, the script keeps the final allocated IP and updates Cloudflare to it. This avoids leaving the hostname pointed at an address that was already released. The command exits with status `3` in that case.

If Cloudflare update fails after OCI rotation, the script does **not** continue rotating. Repair DNS to the replacement IP reported by the command.

## Agent Skill

`SKILL.md` contains instructions suitable for agents that support the Agent Skills layout. The actual mutation logic stays in `scripts/rotate_ip.py` so the operation is deterministic and independently auditable.
