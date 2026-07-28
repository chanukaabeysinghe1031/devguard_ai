"""Module 5 secure file upload and storage tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.exceptions.upload import UnsupportedFileTypeError
from app.domain.services.file_validation import detect_file_type, sanitize_original_filename
from app.domain.services.secret_masker import mask_secrets


async def _register_and_login(auth_client: AsyncClient, email: str) -> tuple[str, str]:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123!",
            "full_name": "Upload Tester",
        },
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    body = login.json()
    return body["access_token"], body["user"]["memberships"][0]["organization_id"]


async def _create_incident(auth_client: AsyncClient, headers: dict) -> str:
    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Upload Proj", "key": "UP", "ci_provider": "github_actions"},
    )
    assert project.status_code == 201, project.text
    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "Upload incident",
            "source": "manual_upload",
            "severity": "high",
        },
    )
    assert incident.status_code == 201, incident.text
    return incident.json()["id"]


def test_sanitize_filename_strips_path_traversal() -> None:
    assert sanitize_original_filename("../../etc/passwd.log") == "passwd.log"
    assert ".." not in sanitize_original_filename("../weird name!!.txt")


def test_zip_extension_rejected() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        detect_file_type("bundle.zip")


def test_secret_masking_redacts_tokens() -> None:
    content = "token=ghp_abcdefghijklmnopqrstuvwxyz123456 password=supersecret"
    masked, count = mask_secrets(content)
    assert count >= 1
    assert "supersecret" not in masked
    assert "ghp_abcdefghijklmnopqrstuvwxyz123456" not in masked


@pytest.mark.asyncio
async def test_upload_list_get_delete_file(auth_client) -> None:
    token, org_id = await _register_and_login(auth_client, f"up-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    incident_id = await _create_incident(auth_client, headers)

    content = b"ERROR: deployment failed\nline 2\n"
    upload = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[("files", ("github-actions.log", content, "text/plain"))],
        data={"file_category": "ci_log", "description": "Failed deploy log"},
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert len(body["files"]) == 1
    file_meta = body["files"][0]
    assert file_meta["original_filename"] == "github-actions.log"
    assert file_meta["file_type"] == "log"
    assert file_meta["validation_status"] == "valid"
    assert file_meta["processing_status"] == "uploaded"
    assert "storage_path" not in file_meta
    file_id = file_meta["id"]

    listed = await auth_client.get(f"/api/v1/incidents/{incident_id}/files", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    detail = await auth_client.get(f"/api/v1/files/{file_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["extracted_metadata"]["line_count"] == 2
    assert "storage_path" not in detail.json()

    deleted = await auth_client.delete(f"/api/v1/files/{file_id}", headers=headers)
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_reject_unsupported_and_empty_and_duplicate(auth_client) -> None:
    token, org_id = await _register_and_login(auth_client, f"rej-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    incident_id = await _create_incident(auth_client, headers)

    empty = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[("files", ("empty.log", b"", "text/plain"))],
    )
    assert empty.status_code == 400
    assert empty.json()["error_code"] == "EMPTY_FILE"

    exe = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[("files", ("malware.exe", b"MZ binary", "application/octet-stream"))],
    )
    assert exe.status_code == 415

    zip_upload = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[("files", ("bundle.zip", b"PK\x03\x04fake", "application/zip"))],
    )
    assert zip_upload.status_code == 415

    payload = b'resource "aws_iam_role" "deploy" {}\n'
    first = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[("files", ("main.tf", payload, "text/plain"))],
    )
    assert first.status_code == 201, first.text

    dup = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[("files", ("main-copy.tf", payload, "text/plain"))],
    )
    assert dup.status_code == 409
    assert dup.json()["error_code"] == "DUPLICATE_FILE"


@pytest.mark.asyncio
async def test_yaml_json_upload_and_analysis_file_association(auth_client) -> None:
    token, org_id = await _register_and_login(auth_client, f"ana-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    incident_id = await _create_incident(auth_client, headers)

    yaml_body = b"name: CI\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
    json_body = b'{"status":"failed","job":"deploy"}\n'

    upload = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[
            ("files", ("workflow.yml", yaml_body, "text/yaml")),
            ("files", ("meta.json", json_body, "application/json")),
        ],
    )
    assert upload.status_code == 201, upload.text
    file_ids = [f["id"] for f in upload.json()["files"]]
    assert len(file_ids) == 2

    analysis = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/analyses",
        headers=headers,
        json={"analysis_type": "full", "file_ids": file_ids},
    )
    assert analysis.status_code == 202, analysis.text
    assert analysis.json()["status"] == "completed"

    # File referenced by analysis cannot be deleted.
    blocked = await auth_client.delete(f"/api/v1/files/{file_ids[0]}", headers=headers)
    assert blocked.status_code == 409

    # Invalid foreign file id rejected.
    bad = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/analyses",
        headers=headers,
        json={"analysis_type": "full", "file_ids": [str(uuid4())]},
    )
    assert bad.status_code == 400
    assert bad.json()["error_code"] == "INVALID_ANALYSIS_FILES"


@pytest.mark.asyncio
async def test_cross_org_file_access_denied(auth_client) -> None:
    owner_token, org_id = await _register_and_login(
        auth_client, f"owner-{uuid4().hex[:8]}@example.com"
    )
    outsider_token, _ = await _register_and_login(auth_client, f"out-{uuid4().hex[:8]}@example.com")
    owner_headers = {
        "Authorization": f"Bearer {owner_token}",
        "X-Organization-Id": org_id,
    }
    incident_id = await _create_incident(auth_client, owner_headers)
    upload = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=owner_headers,
        files=[("files", ("diag.txt", b"plain diagnostic\n", "text/plain"))],
    )
    file_id = upload.json()["files"][0]["id"]

    denied = await auth_client.get(
        f"/api/v1/files/{file_id}",
        headers={
            "Authorization": f"Bearer {outsider_token}",
            "X-Organization-Id": org_id,
        },
    )
    assert denied.status_code == 403
