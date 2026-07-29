"""Generate the DevGuard human-gold retrieval benchmark query set (~120+)."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
BENCH = REPO_ROOT / "datasets" / "benchmark"

# query_id, query_text, technology, failure_category, pipeline_stage,
# expected_technologies, expected_vendors, difficulty, category_group
QUERIES: list[dict[str, Any]] = []


def _q(
    qid: str,
    text: str,
    *,
    technology: str,
    failure_category: str,
    pipeline_stage: str,
    expected_technologies: str,
    expected_vendors: str,
    difficulty: str,
    category_group: str,
) -> None:
    QUERIES.append(
        {
            "query_id": qid,
            "query_text": text,
            "technology": technology,
            "failure_category": failure_category,
            "pipeline_stage": pipeline_stage,
            "expected_technologies": expected_technologies,
            "expected_vendors": expected_vendors,
            "difficulty": difficulty,
            "category_group": category_group,
        }
    )


def _build() -> None:
    QUERIES.clear()

    # Docker (15)
    docker = [
        ("bm-docker-01", "Docker COPY failed because source file is missing", "build", "easy"),
        ("bm-docker-02", "Dockerfile RUN apt-get fails with package not found", "build", "easy"),
        ("bm-docker-03", "Docker build context too large slows CI", "build", "medium"),
        ("bm-docker-04", "Docker image pull rate limit exceeded in pipeline", "deploy", "medium"),
        ("bm-docker-05", "Docker multi-stage build cannot find artifact from previous stage", "build", "hard"),
        ("bm-docker-06", "docker compose up fails with port already allocated", "deploy", "easy"),
        ("bm-docker-07", "Docker ENTRYPOINT script permission denied", "runtime", "medium"),
        ("bm-docker-08", "Docker layer cache not restoring in GitHub Actions", "build", "medium"),
        ("bm-docker-09", "Cannot connect to Docker daemon in CI runner", "build", "medium"),
        ("bm-docker-10", "Docker HEALTHCHECK failing after container start", "runtime", "hard"),
        ("bm-docker-11", "Dockerfile ARG not available during RUN step", "build", "medium"),
        ("bm-docker-12", "Docker push unauthorized authentication required", "deploy", "easy"),
        ("bm-docker-13", "Docker volume mount path does not exist in container", "runtime", "medium"),
        ("bm-docker-14", "Docker Compose depends_on service not healthy", "deploy", "hard"),
        ("bm-docker-15", "Docker build fails with no space left on device", "build", "easy"),
    ]
    for qid, text, stage, diff in docker:
        _q(
            qid,
            text,
            technology="docker",
            failure_category="docker_failure",
            pipeline_stage=stage,
            expected_technologies="docker",
            expected_vendors="Docker",
            difficulty=diff,
            category_group="docker",
        )

    # Terraform (15)
    terraform = [
        ("bm-tf-01", "Terraform undeclared resource reference failure", "plan", "easy"),
        ("bm-tf-02", "Terraform state locked by another process", "apply", "easy"),
        ("bm-tf-03", "Terraform provider authentication failed for AWS", "plan", "medium"),
        ("bm-tf-04", "Terraform cycle error between resources", "plan", "hard"),
        ("bm-tf-05", "Terraform plan shows unexpected destroy for critical resource", "plan", "hard"),
        ("bm-tf-06", "Terraform variable not set required input missing", "plan", "easy"),
        ("bm-tf-07", "Terraform remote backend S3 access denied", "init", "medium"),
        ("bm-tf-08", "Terraform module source not found in registry", "init", "medium"),
        ("bm-tf-09", "Terraform for_each on set of strings invalid", "plan", "medium"),
        ("bm-tf-10", "Terraform apply fails with resource already exists", "apply", "medium"),
        ("bm-tf-11", "Terraform data source returns empty result", "plan", "hard"),
        ("bm-tf-12", "Terraform workspace select failed in CI", "init", "medium"),
        ("bm-tf-13", "Terraform count index out of range", "plan", "hard"),
        ("bm-tf-14", "Terraform import fails for existing cloud resource", "apply", "hard"),
        ("bm-tf-15", "Terraform null_resource provisioner local-exec failed", "apply", "medium"),
    ]
    for qid, text, stage, diff in terraform:
        _q(
            qid,
            text,
            technology="terraform",
            failure_category="terraform_failure",
            pipeline_stage=stage,
            expected_technologies="terraform",
            expected_vendors="Terraform",
            difficulty=diff,
            category_group="terraform",
        )

    # AWS (15)
    aws = [
        ("bm-aws-01", "AWS AccessDenied during deployment", "deploy", "easy"),
        ("bm-aws-02", "AWS IAM role cannot be assumed by service", "deploy", "medium"),
        ("bm-aws-03", "AWS ECS task failed to start AccessDeniedException", "deploy", "medium"),
        ("bm-aws-04", "AWS S3 PutObject Access Denied in pipeline", "deploy", "easy"),
        ("bm-aws-05", "AWS STS AssumeRole with web identity failed", "auth", "hard"),
        ("bm-aws-06", "AWS Lambda permission denied to write CloudWatch logs", "runtime", "medium"),
        ("bm-aws-07", "AWS EKS node cannot pull image from ECR", "deploy", "hard"),
        ("bm-aws-08", "AWS API Gateway authorizer unauthorized", "runtime", "hard"),
        ("bm-aws-09", "AWS credentials not found in environment", "auth", "easy"),
        ("bm-aws-10", "AWS KMS decrypt access denied for secrets", "runtime", "medium"),
        ("bm-aws-11", "AWS CloudFormation stack rollback AccessDenied", "deploy", "medium"),
        ("bm-aws-12", "AWS IAM policy missing s3:GetObject permission", "auth", "easy"),
        ("bm-aws-13", "AWS CodeBuild role insufficient permissions", "build", "medium"),
        ("bm-aws-14", "AWS Secrets Manager GetSecretValue denied", "runtime", "medium"),
        ("bm-aws-15", "AWS VPC endpoint policy blocks service access", "network", "hard"),
    ]
    for qid, text, stage, diff in aws:
        _q(
            qid,
            text,
            technology="aws",
            failure_category="aws_permission_failure",
            pipeline_stage=stage,
            expected_technologies="aws",
            expected_vendors="AWS",
            difficulty=diff,
            category_group="aws",
        )

    # GitHub Actions (15)
    gha = [
        ("bm-gha-01", "GitHub Actions runner offline or not picking jobs", "ci", "easy"),
        ("bm-gha-02", "GitHub Actions workflow_dispatch input not available", "ci", "medium"),
        ("bm-gha-03", "GitHub Actions secrets not injected into job", "ci", "easy"),
        ("bm-gha-04", "GitHub Actions cache restore failed key not found", "ci", "medium"),
        ("bm-gha-05", "GitHub Actions checkout fails authentication", "ci", "easy"),
        ("bm-gha-06", "GitHub Actions matrix job skipped unexpectedly", "ci", "hard"),
        ("bm-gha-07", "GitHub Actions OIDC token request failed", "auth", "hard"),
        ("bm-gha-08", "GitHub Actions self-hosted runner cannot connect", "ci", "medium"),
        ("bm-gha-09", "GitHub Actions workflow syntax error invalid YAML", "ci", "easy"),
        ("bm-gha-10", "GitHub Actions job hangs waiting for environment approval", "ci", "medium"),
        ("bm-gha-11", "GitHub Actions actions/setup-node npm ci hangs", "build", "medium"),
        ("bm-gha-12", "GitHub Actions permissions contents read insufficient", "ci", "medium"),
        ("bm-gha-13", "GitHub Actions reusable workflow call failed", "ci", "hard"),
        ("bm-gha-14", "GitHub Actions artifact upload failed path does not exist", "ci", "easy"),
        ("bm-gha-15", "GitHub Actions concurrency group cancelled in-progress run", "ci", "hard"),
    ]
    for qid, text, stage, diff in gha:
        _q(
            qid,
            text,
            technology="github_actions",
            failure_category="configuration_failure",
            pipeline_stage=stage,
            expected_technologies="github_actions",
            expected_vendors="GitHub Actions",
            difficulty=diff,
            category_group="github_actions",
        )

    # Kubernetes (10)
    k8s = [
        ("bm-k8s-01", "Kubernetes ImagePullBackOff cannot pull container image", "deploy", "easy"),
        ("bm-k8s-02", "Kubernetes CrashLoopBackOff pod keeps restarting", "runtime", "easy"),
        ("bm-k8s-03", "Kubernetes CreateContainerConfigError missing secret", "deploy", "medium"),
        ("bm-k8s-04", "Kubernetes service endpoints empty no ready pods", "runtime", "medium"),
        ("bm-k8s-05", "Kubernetes PVC pending no persistent volume available", "deploy", "medium"),
        ("bm-k8s-06", "Kubernetes liveness probe failed killing container", "runtime", "hard"),
        ("bm-k8s-07", "Kubernetes RBAC forbidden cannot list pods", "auth", "medium"),
        ("bm-k8s-08", "Kubernetes ingress returns 502 bad gateway", "network", "hard"),
        ("bm-k8s-09", "Kubernetes deployment rollout stuck progressing", "deploy", "hard"),
        ("bm-k8s-10", "Kubernetes ConfigMap key not found in volume mount", "deploy", "easy"),
    ]
    for qid, text, stage, diff in k8s:
        _q(
            qid,
            text,
            technology="kubernetes",
            failure_category="deployment_failure",
            pipeline_stage=stage,
            expected_technologies="kubernetes",
            expected_vendors="Kubernetes",
            difficulty=diff,
            category_group="kubernetes",
        )

    # Node (10)
    node = [
        ("bm-node-01", "npm dependency conflict ModuleNotFoundError in CI", "build", "easy"),
        ("bm-node-02", "npm ci fails package-lock out of sync", "build", "easy"),
        ("bm-node-03", "npm ERESOLVE unable to resolve dependency tree", "build", "medium"),
        ("bm-node-04", "Node.js ENGINE unsupported engine version", "build", "easy"),
        ("bm-node-05", "npm ERR! code E401 unauthorized registry", "build", "medium"),
        ("bm-node-06", "Jest test suite fails module not found path alias", "test", "medium"),
        ("bm-node-07", "npm peer dependency warning treated as error", "build", "hard"),
        ("bm-node-08", "Node heap out of memory during webpack build", "build", "medium"),
        ("bm-node-09", "npm publish fails 403 forbidden", "deploy", "medium"),
        ("bm-node-10", "yarn/npm lockfile conflict in monorepo CI", "build", "hard"),
    ]
    for qid, text, stage, diff in node:
        _q(
            qid,
            text,
            technology="node",
            failure_category="dependency_failure",
            pipeline_stage=stage,
            expected_technologies="node",
            expected_vendors="npm|Node.js",
            difficulty=diff,
            category_group="node",
        )

    # Python (10)
    python = [
        ("bm-py-01", "pip install fails dependency resolution conflict", "build", "easy"),
        ("bm-py-02", "Python ModuleNotFoundError in CI virtualenv", "test", "easy"),
        ("bm-py-03", "pytest collection failed import error", "test", "medium"),
        ("bm-py-04", "Poetry lock file out of date in pipeline", "build", "medium"),
        ("bm-py-05", "Python version mismatch pyproject requires-python", "build", "easy"),
        ("bm-py-06", "pip cannot find package version matching specifier", "build", "medium"),
        ("bm-py-07", "Django/Flask migrate fails during deploy", "deploy", "hard"),
        ("bm-py-08", "Python wheel build fails missing system library", "build", "hard"),
        ("bm-py-09", "tox environment failed to recreate", "test", "medium"),
        ("bm-py-10", "uvicorn/gunicorn worker failed to boot", "runtime", "hard"),
    ]
    for qid, text, stage, diff in python:
        _q(
            qid,
            text,
            technology="python",
            failure_category="dependency_failure",
            pipeline_stage=stage,
            expected_technologies="python",
            expected_vendors="Python",
            difficulty=diff,
            category_group="python",
        )

    # Java (10)
    java = [
        ("bm-java-01", "Maven build failure dependency not found", "build", "easy"),
        ("bm-java-02", "Gradle dependency resolution failure", "build", "easy"),
        ("bm-java-03", "Maven surefire tests failed in CI", "test", "medium"),
        ("bm-java-04", "Gradle JVM toolchain version not found", "build", "medium"),
        ("bm-java-05", "Java compilation error package does not exist", "build", "easy"),
        ("bm-java-06", "Maven enforcer plugin ban duplicate classes", "build", "hard"),
        ("bm-java-07", "Gradle OutOfMemoryError during build", "build", "medium"),
        ("bm-java-08", "Spring Boot application failed to start datasource", "runtime", "hard"),
        ("bm-java-09", "Maven settings.xml mirror credentials rejected", "build", "medium"),
        ("bm-java-10", "Java class file major version unsupported", "build", "hard"),
    ]
    for qid, text, stage, diff in java:
        _q(
            qid,
            text,
            technology="java",
            failure_category="build_failure",
            pipeline_stage=stage,
            expected_technologies="java",
            expected_vendors="Apache Maven|Gradle|OpenJDK",
            difficulty=diff,
            category_group="java",
        )

    # Networking (10)
    net = [
        ("bm-net-01", "connection timeout DNS resolution failure in pipeline", "network", "easy"),
        ("bm-net-02", "ECONNREFUSED connecting to internal service", "network", "easy"),
        ("bm-net-03", "TLS handshake failure certificate verify failed", "network", "medium"),
        ("bm-net-04", "proxy authentication required for package registry", "network", "medium"),
        ("bm-net-05", "Git clone fails could not resolve host", "network", "easy"),
        ("bm-net-06", "WebSocket connection dropped behind load balancer", "network", "hard"),
        ("bm-net-07", "HTTP 504 gateway timeout calling upstream API", "network", "medium"),
        ("bm-net-08", "firewall blocks outbound HTTPS from runner", "network", "hard"),
        ("bm-net-09", "IPv6 vs IPv4 connection refused in container", "network", "hard"),
        ("bm-net-10", "self-hosted runner unable to connect after timeout", "network", "medium"),
    ]
    for qid, text, stage, diff in net:
        _q(
            qid,
            text,
            technology="network",
            failure_category="network_failure",
            pipeline_stage=stage,
            expected_technologies="network|github_actions|kubernetes",
            expected_vendors="",
            difficulty=diff,
            category_group="networking",
        )

    # Security (10)
    sec = [
        ("bm-sec-01", "Permission denied while deploying due to IAM policy", "auth", "easy"),
        ("bm-sec-02", "secret scanned and redacted from workflow log", "ci", "medium"),
        ("bm-sec-03", "SSH key permission denied publickey authentication", "auth", "easy"),
        ("bm-sec-04", "container runs as root security policy violated", "runtime", "medium"),
        ("bm-sec-05", "OIDC federation trust policy mismatch", "auth", "hard"),
        ("bm-sec-06", "vulnerable dependency blocked by security gate", "build", "medium"),
        ("bm-sec-07", "TLS certificate expired for ingress endpoint", "network", "easy"),
        ("bm-sec-08", "Kubernetes PodSecurity admission denied", "deploy", "hard"),
        ("bm-sec-09", "AWS security group blocks required port", "network", "medium"),
        ("bm-sec-10", "hardcoded credentials detected in terraform plan", "plan", "medium"),
    ]
    for qid, text, stage, diff in sec:
        _q(
            qid,
            text,
            technology="security",
            failure_category="security_misconfiguration",
            pipeline_stage=stage,
            expected_technologies="aws|kubernetes|terraform|github_actions",
            expected_vendors="AWS|Kubernetes",
            difficulty=diff,
            category_group="security",
        )

    # Configuration (10)
    cfg = [
        ("bm-cfg-01", "Pipeline cache restore failed wrong key configuration", "ci", "easy"),
        ("bm-cfg-02", "environment variable missing in deployment config", "deploy", "easy"),
        ("bm-cfg-03", "YAML indentation error breaks workflow configuration", "ci", "easy"),
        ("bm-cfg-04", "wrong NODE_ENV causes production config in tests", "test", "medium"),
        ("bm-cfg-05", "Helm values override missing required key", "deploy", "medium"),
        ("bm-cfg-06", "feature flag misconfigured disables critical path", "runtime", "hard"),
        ("bm-cfg-07", "CI matrix exclude list removes all jobs", "ci", "hard"),
        ("bm-cfg-08", "dockerfile path incorrect in build config", "build", "easy"),
        ("bm-cfg-09", "service account annotation missing for workload identity", "auth", "hard"),
        ("bm-cfg-10", "logging level misconfigured hides root cause", "runtime", "medium"),
    ]
    for qid, text, stage, diff in cfg:
        _q(
            qid,
            text,
            technology="configuration",
            failure_category="configuration_failure",
            pipeline_stage=stage,
            expected_technologies="github_actions|kubernetes|docker",
            expected_vendors="GitHub Actions|Kubernetes|Docker",
            difficulty=diff,
            category_group="configuration",
        )


def write_assets() -> dict[str, Any]:
    _build()
    BENCH.mkdir(parents=True, exist_ok=True)
    fields = [
        "query_id",
        "query_text",
        "technology",
        "failure_category",
        "pipeline_stage",
        "expected_technologies",
        "expected_vendors",
        "difficulty",
        "category_group",
    ]
    with (BENCH / "queries.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(QUERIES)

    categories = [
        {
            "category_group": "docker",
            "description": "Container build and runtime failures",
            "min_queries": 15,
        },
        {
            "category_group": "terraform",
            "description": "IaC plan/apply failures",
            "min_queries": 15,
        },
        {
            "category_group": "aws",
            "description": "AWS IAM and service permission failures",
            "min_queries": 15,
        },
        {
            "category_group": "github_actions",
            "description": "CI workflow and runner failures",
            "min_queries": 15,
        },
        {
            "category_group": "kubernetes",
            "description": "K8s deploy/runtime failures",
            "min_queries": 10,
        },
        {
            "category_group": "node",
            "description": "Node.js / npm dependency failures",
            "min_queries": 10,
        },
        {
            "category_group": "python",
            "description": "Python packaging and test failures",
            "min_queries": 10,
        },
        {
            "category_group": "java",
            "description": "Maven/Gradle/Java build failures",
            "min_queries": 10,
        },
        {
            "category_group": "networking",
            "description": "DNS/TLS/proxy/connectivity failures",
            "min_queries": 10,
        },
        {
            "category_group": "security",
            "description": "AuthZ/authN and security misconfiguration",
            "min_queries": 10,
        },
        {
            "category_group": "configuration",
            "description": "Pipeline and environment misconfiguration",
            "min_queries": 10,
        },
    ]
    with (BENCH / "categories.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["category_group", "description", "min_queries"]
        )
        writer.writeheader()
        writer.writerows(categories)

    counts: dict[str, int] = {}
    for row in QUERIES:
        counts[row["category_group"]] = counts.get(row["category_group"], 0) + 1

    meta = {
        "benchmark_version": "1.0.0-human-gold",
        "corpus_version_target": "0.5.0-official-docs",
        "query_count": len(QUERIES),
        "category_counts": counts,
        "relevance_scale": {
            "3": "Highly relevant",
            "2": "Relevant",
            "1": "Partially relevant",
            "0": "Not relevant",
        },
        "label_policy": (
            "Official gold_labels.csv must contain human-approved grades only. "
            "AI/retrieval-assisted proposals live in gold_labels.candidates.csv "
            "and review/ until promoted."
        ),
        "collection": "devguard_research_knowledge",
    }
    (BENCH / "benchmark_metadata.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    config = {
        "collection_name": "devguard_research_knowledge",
        "product_collection_forbidden": "devguard_knowledge",
        "candidate_top_k": 20,
        "eval_top_k_default": 5,
        "metrics": [
            "precision@1",
            "precision@3",
            "precision@5",
            "recall@5",
            "recall@10",
            "mrr",
            "map",
            "ndcg@5",
            "ndcg@10",
            "hit_rate",
            "latency_ms",
            "category_accuracy",
            "vendor_coverage",
        ],
        "binary_relevance_threshold": 2,
        "labels_official": "gold_labels.csv",
        "labels_candidates": "gold_labels.candidates.csv",
        "embedding_provider": "sentence_transformers",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_dimension": 384,
        "retriever_version": "research-chroma-minilm-v1",
    }
    (BENCH / "evaluation_config.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    return meta


if __name__ == "__main__":
    print(json.dumps(write_assets(), indent=2))
