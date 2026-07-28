"""Enrich knowledge chunk metadata for hybrid scoring."""

from __future__ import annotations

import hashlib
import re
from typing import Any

_CATEGORY_HINTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_permission_failure", re.compile(r"accessdenied|iam|unauthorized", re.I)),
    ("dependency_failure", re.compile(r"eresolve|npm|dependency|pip", re.I)),
    ("terraform_failure", re.compile(r"terraform|state locked|errorlock", re.I)),
    ("docker_failure", re.compile(r"docker|dockerfile|image", re.I)),
    ("deployment_failure", re.compile(r"deploy|updateservice", re.I)),
    ("build_failure", re.compile(r"build failed|compilation", re.I)),
    ("test_failure", re.compile(r"pytest|test failed", re.I)),
    ("network_failure", re.compile(r"econnrefused|etimedout|timeout", re.I)),
    ("configuration_error", re.compile(r"configuration|invalid config", re.I)),
    ("security_misconfiguration", re.compile(r"security|secret|privilege", re.I)),
)

_TECH_HINTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS", re.compile(r"\baws\b|iam|ecs|s3", re.I)),
    ("Docker", re.compile(r"\bdocker\b", re.I)),
    ("Terraform", re.compile(r"\bterraform\b", re.I)),
    ("npm", re.compile(r"\bnpm\b", re.I)),
    ("Kubernetes", re.compile(r"\bkubernetes\b|\bkubectl\b", re.I)),
)

_ERROR_CODE = re.compile(
    r"\b(AccessDenied|UnauthorizedOperation|ERESOLVE|ErrorLock|StateLocked|"
    r"ECONNREFUSED|ETIMEDOUT|[A-Z][A-Za-z]+Exception)\b"
)
_AWS_SERVICE = re.compile(r"\b(ecs|iam|s3|ec2|lambda|sts|eks)\b", re.I)
_TF_RESOURCE = re.compile(r"\b([a-z]+_[a-z0-9_]+)\b")


def enrich_chunk_metadata(
    *,
    base: dict[str, Any],
    content: str,
    heading: str | None = None,
    document_id: str | None = None,
    chunk_id: str | None = None,
    provider: str | None = None,
    title: str | None = None,
    source_url: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    meta = dict(base)
    meta["document_id"] = document_id or meta.get("document_id") or ""
    meta["chunk_id"] = chunk_id or meta.get("chunk_id") or ""
    meta["title"] = title or meta.get("title") or ""
    meta["source_url"] = source_url or meta.get("source_url") or ""
    meta["version"] = version or meta.get("version") or "1.0"
    meta["provider"] = provider or meta.get("provider") or "general"
    meta["document_status"] = meta.get("document_status") or "active"
    meta["source_type"] = meta.get("source_type") or _infer_source_type(
        meta.get("provider"), source_url
    )
    meta["source_authority"] = meta.get("source_authority") or _infer_authority(
        meta["source_type"], source_url
    )
    meta["heading"] = heading or meta.get("heading") or ""
    meta["content_hash"] = hashlib.sha256((content or "").encode("utf-8")).hexdigest()
    # Never expose private filesystem paths.
    meta.pop("path", None)
    meta.pop("filesystem_path", None)
    meta.pop("storage_path", None)

    text = f"{heading or ''}\n{content or ''}"
    categories = list(meta.get("failure_categories") or [])
    for code, pattern in _CATEGORY_HINTS:
        if pattern.search(text) and code not in categories:
            categories.append(code)
    meta["failure_categories"] = categories[:8]

    technologies = list(meta.get("technologies") or [])
    product = meta.get("product")
    if product and str(product) not in technologies:
        technologies.append(str(product))
    for name, pattern in _TECH_HINTS:
        if pattern.search(text) and name not in technologies:
            technologies.append(name)
    meta["technologies"] = technologies[:10]

    error_codes = list(meta.get("error_codes") or [])
    for match in _ERROR_CODE.finditer(text):
        if match.group(1) not in error_codes:
            error_codes.append(match.group(1))
    meta["error_codes"] = error_codes[:12]

    aws_services = list(meta.get("aws_services") or [])
    for match in _AWS_SERVICE.finditer(text):
        svc = match.group(1).lower()
        if svc not in aws_services:
            aws_services.append(svc)
    meta["aws_services"] = aws_services[:8]

    if "terraform" in text.lower():
        resources = list(meta.get("resource_types") or [])
        for match in _TF_RESOURCE.finditer(text):
            token = match.group(1)
            if token.startswith(("aws_", "google_", "azurerm_")) and token not in resources:
                resources.append(token)
        meta["resource_types"] = resources[:12]

    stages = list(meta.get("pipeline_stages") or [])
    for stage in ("build", "test", "deploy", "plan", "apply", "install"):
        if re.search(rf"\b{stage}\b", text, re.I) and stage not in stages:
            stages.append(stage)
    meta["pipeline_stages"] = stages[:8]
    meta["persist_citation"] = True
    return meta


def _infer_source_type(provider: str | None, source_url: str | None) -> str:
    url = (source_url or "").lower()
    if "docs.aws.amazon.com" in url or "registry.terraform.io" in url:
        return "vendor_documentation"
    if "runbook" in (provider or "").lower():
        return "runbook"
    return "knowledge_document"


def _infer_authority(source_type: str, source_url: str | None) -> str:
    url = (source_url or "").lower()
    if "docs.aws.amazon.com" in url or "docs.docker.com" in url:
        return "official_vendor_documentation"
    if source_type == "vendor_documentation":
        return "vendor_documentation"
    if source_type == "runbook":
        return "verified_internal_runbook"
    return "knowledge_document"
