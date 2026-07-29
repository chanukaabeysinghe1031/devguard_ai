---
provider: docker
title: Docker Build and Registry Errors
product: docker
source_url: https://docs.docker.com/build/building/troubleshooting/
version: 1.0
---

# Docker Failure Guidance

Docker build or pull failures commonly stem from Dockerfile mistakes, missing base images, or registry authentication issues.

## Common signals

- `failed to solve`
- `manifest unknown`
- `pull access denied`
- Cannot connect to the Docker daemon

## Remediation

1. Confirm the base image reference and tag exist.
2. Authenticate to the registry when required.
3. Fix failing RUN instructions and rebuild.
4. Ensure the CI runner has a healthy Docker daemon.
