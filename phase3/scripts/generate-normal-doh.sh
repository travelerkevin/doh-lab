#!/bin/bash
# ============================================================
# Phase 3b: Generate Normal DoH Browsing Traffic (Baseline)
# ============================================================
# Simulates a user browsing the web through a persistent DoH
# client (cloudflared) and captures the resulting DoH traffic
# (TLS to 1.1.1.1:443) to a pcap file.
#
# Design goals (matches how real DoH clients behave):
#   - Persistent TLS connection to the DoH resolver (not per-query)
#   - Query bursts: each "page visit" issues main + subdomain + 3rd-party lookups
#   - Mix of A, AAAA, and HTTPS (type 65) record types
#   - Realistic idle time between page visits (user reading the page)
#
# Run this INSIDE the client container.
#
# Output: /opt/phase3-results/normal_doh.pcap
#
# Usage:
#   bash /opt/phase3-results/scripts/generate-normal-doh.sh [duration_seconds]
#   Default duration: 300 seconds (5 minutes)
# ============================================================

set -e

DURATION="${1:-300}"
DOH_UPSTREAM="https://1.1.1.1/dns-query"
DOH_IP="1.1.1.1"
LOCAL_PORT=5053
OUTPUT_DIR="/opt/phase3-results"
PCAP_FILE="$OUTPUT_DIR/normal_doh.pcap"
LOG_FILE="$OUTPUT_DIR/normal_doh_queries.log"

# --- Domain pools -------------------------------------------------------------

# Main sites a user might "visit" during browsing
MAIN_DOMAINS=(
    wikipedia.org github.com stackoverflow.com reddit.com
    nytimes.com bbc.co.uk cnn.com theverge.com
    medium.com substack.com news.ycombinator.com lobste.rs
    python.org rust-lang.org golang.org nodejs.org
    mozilla.org developer.mozilla.org w3.org rfc-editor.org
    cloudflare.com digitalocean.com aws.amazon.com azure.com
    spotify.com soundcloud.com last.fm bandcamp.com
    twitch.tv youtube.com vimeo.com dailymotion.com
    etsy.com ebay.com amazon.com target.com
    npr.org theguardian.com economist.com wired.com
    arstechnica.com techcrunch.com engadget.com gizmodo.com
    quora.com duckduckgo.com bing.com yandex.com
    weather.com accuweather.com timeanddate.com openweathermap.org
    yelp.com tripadvisor.com booking.com airbnb.com
    linkedin.com dribbble.com behance.net figma.com
    notion.so dropbox.com gitlab.com bitbucket.org
)

# Subdomain prefixes that real sites commonly use
SUBDOMAIN_PREFIXES=(
    www cdn api static img images assets media
    blog shop store help support docs m mobile
    video photo mail login account upload download
    files news search analytics content js css
)

# Third-party domains typically loaded by modern web pages
THIRD_PARTY=(
    fonts.googleapis.com fonts.gstatic.com
    ajax.googleapis.com code.jquery.com
    cdn.jsdelivr.net cdnjs.cloudflare.com unpkg.com
    www.google-analytics.com www.googletagmanager.com
    connect.facebook.net platform.twitter.com
    maps.googleapis.com static.doubleclick.net
    cloudflareinsights.com js.stripe.com
    widget.intercom.io cdn.segment.com
    use.typekit.net cdn.shopify.com
    assets.zendesk.com static.hotjar.com
)

# --- Helpers ------------------------------------------------------------------

cleanup() {
    # Best-effort cleanup of background processes
    [[ -n "${CLOUDFLARED_PID:-}" ]] && kill "$CLOUDFLARED_PID" 2>/dev/null || true
    [[ -n "${TCPDUMP_PID:-}" ]] && kill "$TCPDUMP_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    sync
}
trap cleanup EXIT INT TERM

query() {
    local domain="$1"
    local qtype="${2:-A}"
    dig @127.0.0.1 -p "$LOCAL_PORT" "$domain" "$qtype" \
        +short +time=3 +tries=1 &>/dev/null || true
    QUERY_COUNT=$((QUERY_COUNT + 1))
    printf "[%s] %-5s %s\n" "$(date +%H:%M:%S)" "$qtype" "$domain" >> "$LOG_FILE"
}

pick() {
    # Pick one random element from an array passed by name
    local -n arr=$1
    echo "${arr[$RANDOM % ${#arr[@]}]}"
}

# --- Main ---------------------------------------------------------------------

mkdir -p "$OUTPUT_DIR"

echo "============================================"
echo " Phase 3b: Normal DoH Browsing Baseline"
echo "============================================"
echo "Duration:       ${DURATION}s"
echo "DoH upstream:   $DOH_UPSTREAM"
echo "Local proxy:    127.0.0.1:$LOCAL_PORT"
echo "Output pcap:    $PCAP_FILE"
echo ""

# Dependency check
for tool in tcpdump dig cloudflared; do
    if ! command -v "$tool" &>/dev/null; then
        echo "[!] $tool is not installed in this container"
        exit 1
    fi
done

# Kill any leftovers from previous runs
pkill -f "cloudflared proxy-dns" 2>/dev/null || true
pkill -f "tcpdump -i eth0 -w $PCAP_FILE" 2>/dev/null || true
sleep 1
rm -f "$PCAP_FILE" "$LOG_FILE"

# 1) Start packet capture
echo "[*] Starting packet capture on $DOH_IP:443..."
tcpdump -i eth0 -w "$PCAP_FILE" "host $DOH_IP and tcp port 443" &>/dev/null &
TCPDUMP_PID=$!
sleep 1
if ! kill -0 "$TCPDUMP_PID" 2>/dev/null; then
    echo "[!] tcpdump failed to start (check NET_ADMIN capability)"
    exit 1
fi

# 2) Start persistent DoH proxy (this is the key difference from v1 —
#    cloudflared holds an open TLS connection to 1.1.1.1 and multiplexes
#    all queries over it, exactly like Firefox/Android private DNS.)
echo "[*] Starting cloudflared DoH proxy..."
cloudflared proxy-dns --port "$LOCAL_PORT" --upstream "$DOH_UPSTREAM" &>/dev/null &
CLOUDFLARED_PID=$!
sleep 2
if ! kill -0 "$CLOUDFLARED_PID" 2>/dev/null; then
    echo "[!] cloudflared failed to start"
    exit 1
fi

# 3) Smoke-test the DoH proxy
if ! dig @127.0.0.1 -p "$LOCAL_PORT" example.com +short +time=5 +tries=1 | grep -q .; then
    echo "[!] DoH proxy not resolving — aborting"
    exit 1
fi
echo "[+] DoH proxy is live"
echo ""

# 4) Simulate browsing
: > "$LOG_FILE"
PAGE_COUNT=0
QUERY_COUNT=0
END_TIME=$(( $(date +%s) + DURATION ))

echo "[*] Simulating browsing..."
while [ "$(date +%s)" -lt "$END_TIME" ]; do
    MAIN=$(pick MAIN_DOMAINS)
    PAGE_COUNT=$((PAGE_COUNT + 1))
    printf "\n[Page %d] %s\n" "$PAGE_COUNT" "$MAIN"

    # Main domain: A + AAAA + HTTPS (modern browsers do all three)
    query "$MAIN" A
    query "$MAIN" AAAA
    query "$MAIN" HTTPS

    # Subdomains fetched as the page loads (3-7 per page)
    NUM_SUBS=$(( (RANDOM % 5) + 3 ))
    for _ in $(seq 1 "$NUM_SUBS"); do
        SUB=$(pick SUBDOMAIN_PREFIXES)
        query "${SUB}.${MAIN}" A
    done

    # Third-party resources (2-4 per page)
    NUM_TP=$(( (RANDOM % 3) + 2 ))
    for _ in $(seq 1 "$NUM_TP"); do
        TP=$(pick THIRD_PARTY)
        query "$TP" A
    done

    # Short intra-page delay (browser loading resources in parallel)
    sleep $(( (RANDOM % 2) + 1 ))

    # Inter-page idle: user reads the page (5-30s)
    IDLE=$(( (RANDOM % 26) + 5 ))
    printf "  ... idle %ds\n" "$IDLE"
    sleep "$IDLE"
done

# 5) Stop capture / proxy (also handled by trap)
echo ""
echo "[*] Stopping capture and DoH proxy..."
cleanup
trap - EXIT INT TERM

# 6) Report
if [ -f "$PCAP_FILE" ]; then
    SIZE=$(stat -c %s "$PCAP_FILE" 2>/dev/null || stat -f %z "$PCAP_FILE")
    echo ""
    echo "============================================"
    echo " Baseline capture complete"
    echo "============================================"
    printf "  File:        %s\n"   "$PCAP_FILE"
    printf "  Size:        %d KB\n" "$((SIZE / 1024))"
    printf "  Pages:       %d\n"   "$PAGE_COUNT"
    printf "  DNS queries: %d\n"   "$QUERY_COUNT"
    printf "  Query log:   %s\n"   "$LOG_FILE"
    echo ""
    echo "Next: analyze alongside phase2/doh_bypass.pcap in Phase 3b."
else
    echo "[!] Capture file not created"
    exit 1
fi
