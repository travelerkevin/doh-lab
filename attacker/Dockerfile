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
    git \
    build-essential \
    ruby \
    ruby-dev \
    && rm -rf /var/lib/apt/lists/*

# dnscat2 server for DNS tunneling
RUN git clone https://github.com/iagox86/dnscat2.git /opt/dnscat2 \
    && cd /opt/dnscat2/server \
    && gem install bundler \
    && bundle install

COPY scripts/ /opt/scripts/

CMD ["bash"]
