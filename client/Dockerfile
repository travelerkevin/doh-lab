FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    dnsutils \
    curl \
    wget \
    iputils-ping \
    net-tools \
    tcpdump \
    iptables \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# cloudflared for DoH (Phase 2) — auto-detect architecture (amd64 / arm64)
RUN ARCH=$(dpkg --print-architecture) \
    && wget -q "https://github.com/cloudflare/cloudflared/releases/download/2023.10.0/cloudflared-linux-${ARCH}.deb" \
    && dpkg -i "cloudflared-linux-${ARCH}.deb" \
    && rm "cloudflared-linux-${ARCH}.deb"

CMD ["bash"]
