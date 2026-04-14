#!/bin/bash
# ============================================================
# Phase 3a: Firewall-Level Blocking of Known DoH Resolvers
# ============================================================
# Run this inside the CLIENT container to block outbound DoH
# traffic to known public resolvers, forcing all DNS through
# the enterprise DNS server (10.0.0.10).
#
# Usage:
#   bash /opt/phase3-results/scripts/block-doh.sh apply
#   bash /opt/phase3-results/scripts/block-doh.sh test
#   bash /opt/phase3-results/scripts/block-doh.sh remove
# ============================================================

# Known public DoH resolver IPs
DOH_RESOLVERS=(
    # Cloudflare
    "1.1.1.1"
    "1.0.0.1"
    # Google
    "8.8.8.8"
    "8.8.4.4"
    # Quad9
    "9.9.9.9"
    "149.112.112.112"
    # OpenDNS
    "208.67.222.222"
    "208.67.220.220"
    # NextDNS
    "45.90.28.0/24"
    "45.90.30.0/24"
    # AdGuard
    "94.140.14.14"
    "94.140.15.15"
    # CleanBrowsing
    "185.228.168.168"
    "185.228.169.168"
)

ENTERPRISE_DNS="10.0.0.10"

apply_rules() {
    echo "[*] Phase 3a: Applying DoH firewall blocking rules..."
    echo ""

    # Flush existing OUTPUT rules to start clean
    iptables -F OUTPUT

    # Allow DNS to enterprise DNS server
    iptables -A OUTPUT -d "$ENTERPRISE_DNS" -p udp --dport 53 -j ACCEPT
    iptables -A OUTPUT -d "$ENTERPRISE_DNS" -p tcp --dport 53 -j ACCEPT
    echo "[+] Allowed DNS to enterprise server ($ENTERPRISE_DNS)"

    # Block HTTPS (port 443) to known DoH resolvers
    for ip in "${DOH_RESOLVERS[@]}"; do
        iptables -A OUTPUT -d "$ip" -p tcp --dport 443 -j DROP 2>/dev/null
        echo "[+] Blocked DoH to $ip"
    done

    # Block all outbound plaintext DNS to non-enterprise servers
    iptables -A OUTPUT ! -d "$ENTERPRISE_DNS" -p udp --dport 53 -j DROP
    iptables -A OUTPUT ! -d "$ENTERPRISE_DNS" -p tcp --dport 53 -j DROP
    echo "[+] Blocked all non-enterprise DNS"

    echo ""
    echo "[*] Firewall rules applied. Current OUTPUT chain:"
    iptables -L OUTPUT -n --line-numbers
}

test_rules() {
    echo "============================================"
    echo " Phase 3a: DoH Blocking Verification Tests"
    echo "============================================"
    echo ""
    PASS=0
    FAIL=0

    # Test 1: Enterprise DNS should work
    echo "--- Test 1: Enterprise DNS (should PASS) ---"
    if dig @"$ENTERPRISE_DNS" google.com +short +time=3 +tries=1 2>/dev/null | grep -q .; then
        echo "[PASS] Enterprise DNS resolution works"
        ((PASS++))
    else
        echo "[FAIL] Enterprise DNS resolution failed"
        ((FAIL++))
    fi
    echo ""

    # Test 2: Direct DoH to Cloudflare should be blocked
    echo "--- Test 2: DoH to Cloudflare 1.1.1.1 (should be BLOCKED) ---"
    if curl -s --max-time 5 "https://1.1.1.1/dns-query?name=google.com&type=A" \
        -H "Accept: application/dns-json" 2>/dev/null | grep -q "Answer"; then
        echo "[FAIL] DoH to Cloudflare still works — not blocked"
        ((FAIL++))
    else
        echo "[PASS] DoH to Cloudflare is blocked"
        ((PASS++))
    fi
    echo ""

    # Test 3: Direct DoH to Google should be blocked
    echo "--- Test 3: DoH to Google 8.8.8.8 (should be BLOCKED) ---"
    if curl -s --max-time 5 "https://dns.google/resolve?name=google.com&type=A" \
        --resolve "dns.google:443:8.8.8.8" 2>/dev/null | grep -q "Answer"; then
        echo "[FAIL] DoH to Google still works — not blocked"
        ((FAIL++))
    else
        echo "[PASS] DoH to Google is blocked"
        ((PASS++))
    fi
    echo ""

    # Test 4: cloudflared DoH proxy should fail to resolve
    echo "--- Test 4: cloudflared DoH proxy (should be BLOCKED) ---"
    cloudflared proxy-dns --port 5053 --upstream "https://1.1.1.1/dns-query" &>/dev/null &
    CF_PID=$!
    sleep 2
    if dig @127.0.0.1 -p 5053 google.com +short +time=3 +tries=1 2>/dev/null | grep -q .; then
        echo "[FAIL] cloudflared proxy still resolves — not blocked"
        ((FAIL++))
    else
        echo "[PASS] cloudflared DoH proxy is blocked"
        ((PASS++))
    fi
    kill "$CF_PID" 2>/dev/null
    wait "$CF_PID" 2>/dev/null
    echo ""

    # Test 5: Direct DNS to external server should be blocked
    echo "--- Test 5: Direct DNS to 8.8.8.8:53 (should be BLOCKED) ---"
    if dig @8.8.8.8 google.com +short +time=3 +tries=1 2>/dev/null | grep -q .; then
        echo "[FAIL] External DNS still works — not blocked"
        ((FAIL++))
    else
        echo "[PASS] External DNS is blocked"
        ((PASS++))
    fi
    echo ""

    # Summary
    echo "============================================"
    echo " Results: $PASS passed, $FAIL failed"
    echo "============================================"
    echo ""
    echo "[*] Limitations of IP-based blocking:"
    echo "    - Attackers can self-host DoH servers on arbitrary IPs"
    echo "    - New public DoH providers may not be in the blocklist"
    echo "    - DoH over non-standard ports bypasses port 443 rules"
    echo "    -> This motivates Phase 3b/3c: behavioral traffic analysis"
}

remove_rules() {
    echo "[*] Removing all OUTPUT chain firewall rules..."
    iptables -F OUTPUT
    echo "[+] OUTPUT chain flushed"
    echo ""
    iptables -L OUTPUT -n --line-numbers
}

case "${1:-}" in
    apply)  apply_rules ;;
    test)   test_rules ;;
    remove) remove_rules ;;
    *)
        echo "Phase 3a: Firewall-Level Blocking of Known DoH Resolvers"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  apply   - Apply iptables rules to block known DoH resolvers"
        echo "  test    - Run verification tests against the blocking rules"
        echo "  remove  - Remove all blocking rules (restore original state)"
        echo ""
        echo "Example:"
        echo "  bash $0 apply    # Block DoH resolvers"
        echo "  bash $0 test     # Verify blocking works"
        echo "  bash $0 remove   # Clean up rules"
        exit 1
        ;;
esac
