FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    software-properties-common \
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


# Install wget and gnupg required for fetching the Zeek key
RUN apt-get update && apt-get install -y wget gnupg

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

# Python libraries for Phase 3b (feature extraction + visualization)
# and Phase 3c (ML classification). Non-GUI matplotlib backend.
RUN pip3 install --no-cache-dir \
    scapy \
    pandas \
    numpy \
    matplotlib \
    seaborn \
    scikit-learn \
    xgboost

ENV MPLBACKEND=Agg

# Copy custom Suricata rules
COPY suricata-rules/ /etc/suricata/custom-rules/

CMD ["bash"]
