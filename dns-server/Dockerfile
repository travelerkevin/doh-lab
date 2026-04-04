FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    bind9 \
    bind9-utils \
    dnsutils \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

COPY config/ /etc/bind/

EXPOSE 53/udp 53/tcp

CMD ["named", "-g", "-c", "/etc/bind/named.conf"]
