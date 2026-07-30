"""HMAC-SHA256 webhook signature verification (Phase 5B, ADR-005 §6)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.application.services.github_webhook_security import (
    compute_signature,
    parse_event,
    payload_hash,
    verify_signature,
)
from app.domain.exceptions.integration import WebhookSignatureError

SECRET = "test-secret"
BODY = json.dumps({"action": "completed", "hello": "world"}).encode("utf-8")


def _signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_compute_signature_matches_local_hmac() -> None:
    assert compute_signature(BODY, SECRET) == _signature(BODY, SECRET)


def test_valid_signature_accepted() -> None:
    assert verify_signature(BODY, _signature(BODY, SECRET), secret=SECRET) is True


def test_signature_rejected_for_tampered_body() -> None:
    signature = _signature(BODY, SECRET)
    assert verify_signature(BODY + b" ", signature, secret=SECRET) is False


def test_signature_rejected_for_wrong_secret() -> None:
    assert verify_signature(BODY, _signature(BODY, "other-secret"), secret=SECRET) is False


@pytest.mark.parametrize(
    "header",
    [None, "", "sha1=deadbeef", "deadbeef", "sha256=", "sha256=not-hex"],
)
def test_malformed_signature_headers_rejected(header: str | None) -> None:
    assert verify_signature(BODY, header, secret=SECRET) is False


def test_missing_secret_rejects_everything() -> None:
    assert verify_signature(BODY, _signature(BODY, SECRET), secret="") is False


def test_require_valid_signature_raises() -> None:
    from app.application.services.github_webhook_security import require_valid_signature

    with pytest.raises(WebhookSignatureError):
        require_valid_signature(BODY, "sha256=deadbeef", secret=SECRET)


def test_payload_hash_is_sha256_of_raw_body() -> None:
    assert payload_hash(BODY) == hashlib.sha256(BODY).hexdigest()


def test_parse_event_sanitises_snapshot_without_secrets() -> None:
    raw = json.dumps(
        {
            "action": "completed",
            "installation": {"id": 42, "account": {"login": "acme"}},
            "repository": {"id": 7, "full_name": "acme/api", "default_branch": "main"},
            "workflow_run": {
                "id": 900,
                "name": "CI",
                "conclusion": "failure",
                "head_branch": "main",
                "head_sha": "abc123",
            },
            "sender": {"login": "octocat", "email": "secret@example.com"},
        }
    ).encode("utf-8")

    event = parse_event(raw_body=raw, event_name="workflow_run", delivery_id="delivery-1")

    assert event.delivery_id == "delivery-1"
    assert event.event_name == "workflow_run"
    assert event.event_action == "completed"
    assert event.installation_id == 42
    assert event.repository_id == 7
    assert event.is_ingestible_run is True
    assert event.snapshot["workflow_run"]["conclusion"] == "failure"
    assert "sender" not in event.snapshot
    assert "secret@example.com" not in json.dumps(event.snapshot)


def test_parse_event_falls_back_to_payload_hash_when_delivery_header_missing() -> None:
    event = parse_event(raw_body=BODY, event_name="workflow_run", delivery_id=None)
    assert event.delivery_id == payload_hash(BODY)


def test_unsupported_event_flagged() -> None:
    event = parse_event(raw_body=b"{}", event_name="push", delivery_id="d2")
    assert event.is_supported is False
    assert event.is_ingestible_run is False
