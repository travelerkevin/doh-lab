# DoH Security Lab: DNS over HTTPS Attack and Defense

## Overview

This project explores how DNS over HTTPS (DoH) can be exploited to bypass enterprise security monitoring, and what defenders can do about it. We build a Dockerized lab environment to demonstrate the full attack-defense lifecycle across three phases.

## Lab Architecture

Four Docker containers on a shared network (`10.0.0.0/24`):

| Container | IP | Role | Key Tools |
|-----------|------|------|-----------|
| `dns-server` | 10.0.0.10 | Enterprise DNS server | BIND9 |
| `client` | 10.0.0.20 | Internal client machine | dig, curl, cloudflared |
| `attacker` | 10.0.0.30 | Attack node / C2 server | dnscat2 |
| `monitor` | 10.0.0.40 | Network monitor | Suricata, Zeek, tshark |

## Project Phases

### Phase 1: Traditional DNS Attack Detection

**Goal:** Demonstrate that DNS tunneling over plaintext DNS is easily detected.

- Set up BIND9 as the enterprise DNS resolver
- Use dnscat2 to establish a DNS tunnel between `attacker` and `client`
- Encode C2 commands and data exfiltration payloads into DNS queries (Base64-encoded subdomains, TXT records)
- Suricata rules detect anomalies: abnormal subdomain length, unusual query frequency, oversized TXT responses
- **Output:** Attack traffic pcap + Suricata alerts showing successful detection

### Phase 2: DoH Bypass Demonstration

**Goal:** Show that the same attacks become invisible when wrapped in DoH.

- Configure the client to use DoH (via cloudflared) pointing to a public resolver (1.1.1.1)
- Replicate the exact same DNS tunneling attack from Phase 1, now over DoH
- Show that Suricata generates zero alerts — all traffic appears as normal HTTPS on port 443
- Capture traffic from the monitor to visualize the difference: plaintext DNS queries vs opaque TLS streams
- Generate normal DoH browsing traffic as a baseline for comparison in Phase 3
- **Output:** Side-by-side comparison of monitor logs (Phase 1 alerts vs Phase 2 silence)

### Phase 3: Countermeasures Without Decryption

**Goal:** Explore detection methods that work on encrypted DoH traffic.

**3a. Firewall-Level Blocking**
- Block known public DoH resolver IPs at the firewall level
- Force all DNS resolution through the enterprise DNS server
- Discuss limitations: attackers can self-host DoH servers to bypass IP blocklists

**3b. Traffic Metadata Analysis**
- Use Zeek/tshark to extract flow-level features from captured traffic:
  - Packet size mean and variance
  - Request interval and timing patterns
  - Upload vs download byte ratio
  - Connection duration
- Compare feature distributions between normal DoH browsing and DoH tunneling
- Visualize the differences with plots

**3c. ML-Based Classification (Stretch Goal)**
- Export extracted features to CSV
- Train a classifier (XGBoost or Random Forest) to distinguish normal DoH vs DoH tunneling
- Evaluate with confusion matrix and standard metrics
- Demonstrate that behavioral analysis can detect DoH abuse without decryption

**Output:** Detection results, visualizations, and analysis report

## Team Division

| Member | Responsibility |
|--------|---------------|
| Member A | Phase 1 — DNS server setup, attack execution, Suricata rules |
| Member B | Phase 2 — DoH configuration, bypass demonstration, traffic comparison |
| Member C | Phase 3 — Firewall rules, metadata extraction, ML classification |

**Shared:** Docker Compose environment, final presentation and report

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed
  - macOS: Download and install directly
  - Windows: Install Docker Desktop with WSL2 backend enabled
  - Linux: Install Docker Engine and Docker Compose
- [Git](https://git-scm.com/downloads) installed
- ~4GB free disk space

### Clone and Run

```bash
# Clone the repository
git clone https://github.com/travelerkevin/doh-lab.git
cd doh-lab

# Build and start all four containers
docker compose up -d --build

# Verify all containers are running
docker compose ps
```

You should see four containers running: `dns-server`, `client`, `attacker`, `monitor`.

### Access Containers

Open separate terminal windows and enter the container you need:

```bash
# Enter the DNS server
docker exec -it dns-server bash

# Enter the client
docker exec -it client bash

# Enter the attacker
docker exec -it attacker bash

# Enter the monitor
docker exec -it monitor bash
```

### Verify the Environment

From inside the `client` container:

```bash
# Test DNS resolution through enterprise DNS server
dig @10.0.0.10 google.com

# Ping other containers
ping -c 3 10.0.0.10    # dns-server
ping -c 3 10.0.0.30    # attacker
ping -c 3 10.0.0.40    # monitor
```

### Stop the Lab

```bash
# Stop all containers
docker compose down

# Stop and remove all data (full reset)
docker compose down -v --rmi all
```

## Daily Workflow

```bash
# Before you start working, pull the latest changes
git pull

# Rebuild if any Dockerfile was updated
docker compose up -d --build

# After you finish, push your changes
git add .
git commit -m "describe what you changed"
git push
```

## Project Structure

```
doh-lab/
├── docker-compose.yml          # Container orchestration
├── .gitignore
├── README.md
├── dns-server/
│   ├── Dockerfile              # BIND9 DNS server
│   └── config/
│       └── named.conf          # BIND9 configuration
├── client/
│   └── Dockerfile              # Client with dig, curl, cloudflared
├── attacker/
│   ├── Dockerfile              # Attacker with dnscat2
│   └── scripts/                # Attack scripts
├── monitor/
│   ├── Dockerfile              # Suricata + Zeek
│   ├── suricata-rules/         # Custom detection rules
│   │   └── dns-tunnel.rules
│   └── zeek-scripts/           # Traffic analysis scripts
├── phase1/                     # Phase 1 results and pcaps
├── phase2/                     # Phase 2 results and pcaps
├── phase3/                     # Phase 3 analysis and ML code
└── docs/                       # Presentation and report
```


- If containers cannot reach the internet, restart Docker Desktop
