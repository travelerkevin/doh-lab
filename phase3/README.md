# Phase 3: Countermeasures Without Decryption

## Phase 3a: Firewall-Level Blocking

### Objective

Block known public DoH resolver IPs at the firewall level, forcing all DNS resolution through the enterprise DNS server. This demonstrates the simplest countermeasure against DoH bypass, along with its limitations.

### Prerequisites

- All four containers running: `docker compose up -d --build`
- Phase 3 volume is mounted on the client container at `/opt/phase3-results/`

### How It Works

The script applies three layers of iptables rules on the **client** container:

1. **Allow enterprise DNS** — Permit DNS (port 53) to the enterprise server (10.0.0.10)
2. **Block known DoH IPs** — Drop HTTPS (port 443) traffic to known public DoH resolvers (Cloudflare, Google, Quad9, OpenDNS, NextDNS, AdGuard, CleanBrowsing)
3. **Block external DNS** — Drop all DNS (port 53) traffic to any non-enterprise server

### Step-by-Step Procedure

#### Step 1: Enter the Client Container

```bash
docker exec -it client bash
```

#### Step 2: Apply Blocking Rules

```bash
bash /opt/phase3-results/scripts/block-doh.sh apply
```

Expected output: a list of iptables rules showing each blocked IP and the enterprise DNS allow rule.

#### Step 3: Run Verification Tests

```bash
bash /opt/phase3-results/scripts/block-doh.sh test
```

This runs 5 tests:

| Test | What It Checks | Expected Result |
|------|---------------|-----------------|
| 1 | Enterprise DNS resolution via 10.0.0.10 | PASS (works) |
| 2 | DoH request to Cloudflare (1.1.1.1:443) | PASS (blocked) |
| 3 | DoH request to Google (8.8.8.8:443) | PASS (blocked) |
| 4 | cloudflared DoH proxy to 1.1.1.1 | PASS (blocked) |
| 5 | Direct DNS to external server 8.8.8.8:53 | PASS (blocked) |

#### Step 4: Clean Up

```bash
bash /opt/phase3-results/scripts/block-doh.sh remove
```

### Blocked DoH Resolvers

| Provider | IPs |
|----------|-----|
| Cloudflare | 1.1.1.1, 1.0.0.1 |
| Google | 8.8.8.8, 8.8.4.4 |
| Quad9 | 9.9.9.9, 149.112.112.112 |
| OpenDNS | 208.67.222.222, 208.67.220.220 |
| NextDNS | 45.90.28.0/24, 45.90.30.0/24 |
| AdGuard | 94.140.14.14, 94.140.15.15 |
| CleanBrowsing | 185.228.168.168, 185.228.169.168 |

### Limitations

IP-based blocking is a necessary first step but has fundamental weaknesses:

1. **Self-hosted DoH servers** — An attacker can run their own DoH server on any IP address not in the blocklist
2. **Incomplete blocklists** — New DoH providers appear regularly and may not be covered
3. **Non-standard ports** — DoH can run on any port, not just 443
4. **IP churn** — Cloud-hosted DoH resolvers may change IPs over time

These limitations motivate **Phase 3b** (traffic metadata analysis) and **Phase 3c** (ML-based classification), which detect DoH abuse through behavioral patterns rather than IP addresses.
