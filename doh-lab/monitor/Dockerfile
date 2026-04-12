FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    software-properties-common \
    wget \
    && add-apt-repository ppa:oisf/suricata-stable \
    && apt-get update && apt-get install -y \
    suricata \
    tshark \
    tcpdump \
    iputils-ping \
    net-tools \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Zeek
RUN echo 'deb http://download.opensuse.org/repositories/security:/zeek/xUbuntu_22.04/ /' \
    > /etc/apt/sources.list.d/zeek.list \
    && wget -qO - https://download.opensuse.org/repositories/security:/zeek/xUbuntu_22.04/Release.key \
    | apt-key add - \
    && apt-get update && apt-get install -y zeek \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/zeek/bin:${PATH}"

# Create log directories
RUN mkdir -p /var/log/suricata /var/log/zeek

# Copy custom Suricata rules
COPY suricata-rules/ /etc/suricata/custom-rules/

# Add custom rules to Suricata config
RUN python3 -c "content = open('/etc/suricata/suricata.yaml').read(); content = content.replace('rule-files:\n  - suricata.rules', 'rule-files:\n  - suricata.rules\n  - /etc/suricata/custom-rules/dns-tunnel.rules', 1); open('/etc/suricata/suricata.yaml', 'w').write(content)"

CMD ["bash"]
