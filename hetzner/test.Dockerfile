FROM hashicorp/terraform:1.14.0 AS terraform
FROM golang:1.26.11
COPY --from=terraform /bin/terraform /usr/local/bin/terraform
RUN apt-get update && apt-get install -y --no-install-recommends iptables iproute2 && rm -rf /var/lib/apt/lists/*
ENV JNPT_ADAPTER_TESTS=1
WORKDIR /src
CMD ["go", "test", "-v", "./hetzner/..."]
