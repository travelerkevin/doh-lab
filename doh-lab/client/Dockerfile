FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    dnsutils \
    curl \
    wget \
    iputils-ping \
    net-tools \
    tcpdump \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# cloudflared for DoH (Phase 2)
RUN wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb \
    && dpkg -i cloudflared-linux-amd64.deb \
    && rm cloudflared-linux-amd64.deb

CMD ["bash"]
