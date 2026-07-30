"""GitHub webhook signature verification and payload sanitisation (ADR-005 §6)."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

import structlog

from app.domain.exceptions.integration import WebhookSignatureError

logger = structlog.get_logger(__name__)

SIGNATURE_HEADER = "X-Hub-Signature-256"
DELIVERY_HEADER = "X-GitHub-Delivery"
EVENT_HEADER = "X-GitHub-Event"
_SIGNATURE_PREFIX = "sha256="

# Events processed by Phase 5B. Anything else is recorded and ignored.
SUPPORTED_EVENTS = frozenset({"workflow_run", "installation", "installation_repositories", "ping"})
INGESTION_EVENT = "workflow_run"
INGESTION_ACTION = "completed"

_MAX_TEXT = 500


def compute_signature(raw_body: bytes, secret: str) -> str:
    """Return the ``sha256=...`` header value GitHub would send for this body."""
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"{_SIGNATURE_PREFIX}{digest}"


def verify_signature(raw_body: bytes, signature_header: str | None, *, secret: str) -> bool:
    """Constant-time HMAC-SHA256 verification of the raw request body."""
    if not secret or not signature_header:
        return False
    header = signature_header.strip()
    if not header.startswith(_SIGNATURE_PREFIX):
        return False
    return hmac.compare_digest(header, compute_signature(raw_body, secret))


def require_valid_signature(raw_body: bytes, signature_header: str | None, *, secret: str) -> None:
    if not verify_signature(raw_body, signature_header, secret=secret):
        logger.warning("github_webhook_signature_rejected")
        raise WebhookSignatureError()


def payload_hash(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def parse_payload(raw_body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = "".join(char for char in value if char.isprintable()).strip()
    return cleaned[:_MAX_TEXT] or None


@dataclass(frozen=True, slots=True)
class ParsedWebhookEvent:
    """Signature-validated, sanitised view of an inbound webhook."""

    delivery_id: str
    event_name: str
    event_action: str | None
    installation_id: int | None
    repository_id: int | None
    snapshot: dict[str, Any]

    @property
    def is_supported(self) -> bool:
        return self.event_name in SUPPORTED_EVENTS

    @property
    def is_ingestible_run(self) -> bool:
        return self.event_name == INGESTION_EVENT and self.event_action == INGESTION_ACTION


def build_sanitised_snapshot(event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Extract only identifiers, names, and conclusions — never the full body."""
    repository = payload.get("repository") or {}
    installation = payload.get("installation") or {}
    snapshot: dict[str, Any] = {
        "event": event_name,
        "action": _text(payload.get("action")),
        "installation": {
            "id": _int_or_none(installation.get("id")),
            "account_login": _text((installation.get("account") or {}).get("login")),
        },
        "repository": {
            "id": _int_or_none(repository.get("id")),
            "full_name": _text(repository.get("full_name")),
            "default_branch": _text(repository.get("default_branch")),
        },
    }

    run = payload.get("workflow_run")
    if isinstance(run, dict):
        actor = run.get("actor") or {}
        snapshot["workflow_run"] = {
            "id": _int_or_none(run.get("id")),
            "name": _text(run.get("name")),
            "workflow_id": _int_or_none(run.get("workflow_id")),
            "run_number": _int_or_none(run.get("run_number")),
            "run_attempt": _int_or_none(run.get("run_attempt")),
            "event": _text(run.get("event")),
            "status": _text(run.get("status")),
            "conclusion": _text(run.get("conclusion")),
            "head_branch": _text(run.get("head_branch")),
            "head_sha": _text(run.get("head_sha")),
            "html_url": _text(run.get("html_url")),
            "run_started_at": _text(run.get("run_started_at")),
            "updated_at": _text(run.get("updated_at")),
            "actor_login": _text(actor.get("login")),
        }

    workflow = payload.get("workflow")
    if isinstance(workflow, dict):
        snapshot["workflow"] = {
            "id": _int_or_none(workflow.get("id")),
            "name": _text(workflow.get("name")),
            "path": _text(workflow.get("path")),
        }
    return snapshot


def parse_event(
    *,
    raw_body: bytes,
    event_name: str | None,
    delivery_id: str | None,
) -> ParsedWebhookEvent:
    payload = parse_payload(raw_body)
    name = (event_name or "unknown").strip()[:80]
    snapshot = build_sanitised_snapshot(name, payload)
    repository = snapshot.get("repository") or {}
    installation = snapshot.get("installation") or {}
    return ParsedWebhookEvent(
        delivery_id=(delivery_id or payload_hash(raw_body))[:128],
        event_name=name,
        event_action=snapshot.get("action"),
        installation_id=installation.get("id"),
        repository_id=repository.get("id"),
        snapshot=snapshot,
    )
