FROM golang:1.26.11
RUN apt-get update && apt-get install -y --no-install-recommends iptables iproute2 strace systemd && rm -rf /var/lib/apt/lists/*
ENV JNPT_ADAPTER_TESTS=1
WORKDIR /src
CMD ["go", "test", "-v", "./..."]
