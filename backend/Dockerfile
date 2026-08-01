FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Base OS packages (required for health/curl). Optional verifier CLIs installed best-effort below.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional verifiers — install best-effort; runtime returns UNAVAILABLE if missing.
# Do not fail the image build when downloads fail. Never required for container healthcheck.
ARG TERRAFORM_VERSION=1.9.8
ARG ACTIONLINT_VERSION=1.7.7
ARG OPA_VERSION=0.70.0
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && ( \
        curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
          -o /tmp/terraform.zip \
        && unzip -o /tmp/terraform.zip -d /usr/local/bin \
        && chmod +x /usr/local/bin/terraform \
        && rm -f /tmp/terraform.zip \
      ) || echo "optional terraform install skipped"; \
    ( \
        curl -fsSL "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_amd64.tar.gz" \
          -o /tmp/actionlint.tgz \
        && tar -xzf /tmp/actionlint.tgz -C /usr/local/bin actionlint \
        && chmod +x /usr/local/bin/actionlint \
        && rm -f /tmp/actionlint.tgz \
      ) || echo "optional actionlint install skipped"; \
    ( \
        curl -fsSL "https://github.com/open-policy-agent/opa/releases/download/v${OPA_VERSION}/opa_linux_amd64_static" \
          -o /usr/local/bin/opa \
        && chmod +x /usr/local/bin/opa \
      ) || echo "optional opa install skipped"; \
    pip install --no-cache-dir "checkov==3.2.334" || echo "optional checkov install skipped"; \
    apt-get clean && rm -rf /var/lib/apt/lists/* || true

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
