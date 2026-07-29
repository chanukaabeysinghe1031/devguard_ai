#!/usr/bin/env python3
"""Phase 5 local release-candidate validation harness (API + AI journey)."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:18000/api/v1"  # overwritten
BASE = "http://127.0.0.1:8000/api/v1"
OUT = Path("reports/phase5")
OUT.mkdir(parents=True, exist_ok=True)
FIXTURES = Path("/tmp/phase5_logs")

EMAIL = f"phase5_{uuid.uuid4().hex[:8]}@example.com"
PASSWORD = "Phase5SecurePass123!"


def req(
    method: str,
    path: str,
    *,
    data: dict | None = None,
    token: str | None = None,
    org: str | None = None,
    form_bytes: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 120,
) -> tuple[int, Any]:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if org:
        headers["X-Organization-Id"] = str(org)
    body: bytes | None = None
    if form_bytes is not None:
        body = form_bytes
        if content_type:
            headers["Content-Type"] = content_type
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    request = Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload
    except URLError as exc:
        return 0, {"error": str(exc)}


def multipart(file_path: Path) -> tuple[bytes, str]:
    boundary = f"----phase5{uuid.uuid4().hex}"
    content = file_path.read_bytes()
    parts = [
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{file_path.name}"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode()
        + content
        + b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def timed(label: str, fn):
    started = time.perf_counter()
    result = fn()
    ms = (time.perf_counter() - started) * 1000
    return result, ms


def main() -> int:
    report: dict[str, Any] = {
        "email": EMAIL,
        "journey": [],
        "ai": [],
        "errors": [],
        "performance": {},
        "bugs": [],
    }

    # --- Auth journey ---
    (status, body), ms = timed(
        "register",
        lambda: req(
            "POST",
            "/auth/register",
            data={"email": EMAIL, "password": PASSWORD, "full_name": "Phase5 Tester"},
        ),
    )
    report["performance"]["register_ms"] = ms
    report["journey"].append({"step": "register", "status": status, "ok": status == 201})
    (status, body), ms = timed(
        "login",
        lambda: req("POST", "/auth/login", data={"email": EMAIL, "password": PASSWORD}),
    )
    report["performance"]["login_ms"] = ms
    if status != 200:
        report["bugs"].append(
            {
                "id": "BUG-AUTH-LOGIN",
                "description": "Login failed after register",
                "actual": body,
            }
        )
        (OUT / "phase5_report.json").write_text(json.dumps(report, indent=2))
        return 1
    token = body["access_token"]
    refresh = body["refresh_token"]
    org_id = body["user"]["memberships"][0]["organization_id"]
    report["journey"].append({"step": "login", "status": status, "ok": True})

    status, me = req("GET", "/auth/me", token=token)
    report["journey"].append({"step": "me", "status": status, "ok": status == 200})

    status, logout = req("POST", "/auth/logout", data={"refresh_token": refresh}, token=token)
    report["journey"].append({"step": "logout", "status": status, "ok": status in {200, 204}})

    status, body2 = req("POST", "/auth/login", data={"email": EMAIL, "password": PASSWORD})
    token = body2["access_token"]
    refresh = body2["refresh_token"]
    org_id = body2["user"]["memberships"][0]["organization_id"]
    report["journey"].append({"step": "login_again", "status": status, "ok": status == 200})

    # Expired/invalid token behaviour
    status, bad = req("GET", "/auth/me", token="invalid.token.value")
    report["errors"].append(
        {
            "case": "invalid_token",
            "status": status,
            "ok": status == 401,
            "body_keys": list(bad.keys()) if isinstance(bad, dict) else type(bad).__name__,
            "has_stack": "Traceback" in str(bad),
        }
    )

    # --- Project journey ---
    status, project = req(
        "POST",
        "/projects",
        token=token,
        org=org_id,
        data={
            "name": "Phase5 Project",
            "key": f"P5{uuid.uuid4().hex[:4].upper()}",
            "ci_provider": "github_actions",
            "description": "RC validation",
        },
    )
    report["journey"].append({"step": "create_project", "status": status, "ok": status == 201})
    project_id = project["id"] if isinstance(project, dict) else None

    if project_id:
        status, edited = req(
            "PATCH",
            f"/projects/{project_id}",
            token=token,
            org=org_id,
            data={"description": "Updated by Phase 5"},
        )
        report["journey"].append({"step": "edit_project", "status": status, "ok": status == 200})

        # Archive instead of hard delete if delete unsupported
        status, archived = req(
            "POST",
            f"/projects/{project_id}/archive",
            token=token,
            org=org_id,
            data={},
        )
        report["journey"].append(
            {"step": "archive_project", "status": status, "ok": status in {200, 201}}
        )
        status, restored = req(
            "POST",
            f"/projects/{project_id}/restore",
            token=token,
            org=org_id,
            data={},
        )
        report["journey"].append(
            {"step": "restore_project", "status": status, "ok": status in {200, 201}}
        )

    # --- Incident journey ---
    status, incident = req(
        "POST",
        "/incidents",
        token=token,
        org=org_id,
        data={
            "project_id": project_id,
            "title": "Phase5 base incident",
            "source": "manual_upload",
            "severity": "high",
            "description": "RC journey",
        },
    )
    report["journey"].append({"step": "create_incident", "status": status, "ok": status == 201})
    incident_id = incident["id"] if isinstance(incident, dict) else None
    if incident_id:
        status, _ = req(
            "PATCH",
            f"/incidents/{incident_id}",
            token=token,
            org=org_id,
            data={"title": "Phase5 base incident (edited)"},
        )
        report["journey"].append({"step": "edit_incident", "status": status, "ok": status == 200})

    # --- Upload error cases ---
    empty = FIXTURES / "empty.log"
    empty.write_text("")
    body_bytes, ctype = multipart(empty)
    status, up = req(
        "POST",
        f"/incidents/{incident_id}/files",
        token=token,
        org=org_id,
        form_bytes=body_bytes,
        content_type=ctype,
    )
    report["errors"].append(
        {
            "case": "empty_file",
            "status": status,
            "ok": status in {400, 422},
            "detail": str(up)[:300],
            "secrets_leaked": "sk-" in str(up).lower(),
        }
    )

    bad_exe = FIXTURES / "payload.exe"
    bad_exe.write_bytes(b"MZ fake exe")
    body_bytes, ctype = multipart(bad_exe)
    status, up = req(
        "POST",
        f"/incidents/{incident_id}/files",
        token=token,
        org=org_id,
        form_bytes=body_bytes,
        content_type=ctype,
    )
    report["errors"].append(
        {
            "case": "unsupported_file",
            "status": status,
            "ok": status in {400, 415, 422},
            "detail": str(up)[:300],
        }
    )

    # --- AI scenarios ---
    scenarios = [
        ("aws_access_denied.log", "aws_permission_failure", True),
        ("terraform_undeclared.log", "terraform_failure", True),
        ("docker_copy.log", "docker_failure", True),
        ("gha_runner_offline.log", "ci_runner_failure", True),
        ("k8s_imagepull.log", "deployment_failure", True),
        ("maven_dep.log", "build_failure", True),
        ("gradle_dep.log", "build_failure", True),
        ("python_module.log", "dependency_failure", True),
        ("npm_eresolve.log", "dependency_failure", True),
        ("unknown.log", "unknown_failure", True),
        ("success_pipeline.log", "unknown_failure", False),
    ]

    for filename, expected_category, expect_failure in scenarios:
        path = FIXTURES / filename
        # fresh incident per analysis
        status, inc = req(
            "POST",
            "/incidents",
            token=token,
            org=org_id,
            data={
                "project_id": project_id,
                "title": f"Phase5 {filename}",
                "source": "manual_upload",
                "severity": "medium",
            },
        )
        if status != 201:
            report["ai"].append({"file": filename, "ok": False, "error": f"incident {status}"})
            continue
        iid = inc["id"]
        body_bytes, ctype = multipart(path)
        (status, uploaded), upload_ms = timed(
            "upload",
            lambda: req(
                "POST",
                f"/incidents/{iid}/files",
                token=token,
                org=org_id,
                form_bytes=body_bytes,
                content_type=ctype,
            ),
        )
        if status != 201:
            report["ai"].append({"file": filename, "ok": False, "error": f"upload {status} {uploaded}"})
            continue
        file_id = uploaded["files"][0]["id"]
        (status, started), start_ms = timed(
            "analyse",
            lambda: req(
                "POST",
                f"/incidents/{iid}/analyses",
                token=token,
                org=org_id,
                data={
                    "analysis_type": "full",
                    "file_ids": [file_id],
                    "options": {
                        "enable_rag": True,
                        "enable_llm": True,
                        "generate_recommendations": True,
                        "execution_mode": "rag_llm",
                        "retrieval_mode": "embedding_only",
                    },
                },
            ),
        )
        aid = started.get("analysis_run_id") if isinstance(started, dict) else None
        final_status = started.get("status") if isinstance(started, dict) else None
        poll_ms = 0.0
        if aid and final_status not in {"completed", "failed"}:
            t0 = time.perf_counter()
            for _ in range(90):
                st, det = req("GET", f"/analyses/{aid}/status", token=token, org=org_id)
                if isinstance(det, dict) and det.get("status") in {"completed", "failed"}:
                    final_status = det["status"]
                    break
                time.sleep(1)
            poll_ms = (time.perf_counter() - t0) * 1000

        detail = {}
        evidence = []
        sources = []
        recs = []
        if aid:
            _, detail = req("GET", f"/analyses/{aid}", token=token, org=org_id)
            _, evidence_payload = req("GET", f"/analyses/{aid}/evidence", token=token, org=org_id)
            _, sources_payload = req("GET", f"/analyses/{aid}/sources", token=token, org=org_id)
            _, recs_payload = req(
                "GET", f"/analyses/{aid}/recommendations", token=token, org=org_id
            )
            evidence = evidence_payload.get("items", []) if isinstance(evidence_payload, dict) else []
            sources = sources_payload.get("items", []) if isinstance(sources_payload, dict) else []
            recs = recs_payload.get("items", []) if isinstance(recs_payload, dict) else []

        classification = (detail or {}).get("classification") or {}
        category = classification.get("category") or classification.get("predicted_category")
        # Some responses nest differently
        if not category and isinstance(detail.get("prediction"), dict):
            category = detail["prediction"].get("predicted_category") or detail["prediction"].get(
                "category"
            )
        if not category and isinstance(detail.get("output_summary"), dict):
            category = (
                detail["output_summary"].get("primary_category")
                or (detail["output_summary"].get("classification") or {}).get("category")
            )
        confidence = classification.get("confidence")
        root = (detail or {}).get("root_cause") or {}
        summary = root.get("summary") or ""
        hallucinated = any(
            term in summary.lower()
            for term in ["http://example.invalid", "made-up-doc", "lorem ipsum"]
        )
        ok = (
            final_status == "completed"
            and category == expected_category
            and (len(evidence) >= 1 if expect_failure else True)
            and not hallucinated
        )
        row = {
            "file": filename,
            "expected_category": expected_category,
            "actual_category": category,
            "status": final_status,
            "confidence": confidence,
            "evidence_count": len(evidence),
            "sources_count": len(sources),
            "recommendations_count": len(recs),
            "root_cause_summary": summary[:240],
            "upload_ms": upload_ms,
            "start_ms": start_ms,
            "poll_ms": poll_ms,
            "error_message": (detail or {}).get("error_message"),
            "ok": ok,
            "category_ok": category == expected_category,
            "completed": final_status == "completed",
        }
        report["ai"].append(row)
        print(
            f"[{'PASS' if ok else 'FAIL'}] {filename}: {category} "
            f"(expected {expected_category}) status={final_status} "
            f"ev={len(evidence)} src={len(sources)} rec={len(recs)}"
        )

    # Persistence spot-check: list incidents
    status, incidents = req("GET", "/incidents?page=1&page_size=20", token=token, org=org_id)
    report["journey"].append(
        {
            "step": "list_incidents_persistence",
            "status": status,
            "ok": status == 200 and isinstance(incidents, dict) and len(incidents.get("items", [])) > 0,
            "count": len(incidents.get("items", [])) if isinstance(incidents, dict) else 0,
        }
    )

    # Frontend history persistence note (client-only state)
    report["bugs"].append(
        {
            "id": "BUG-UI-HISTORY-SESSION",
            "severity": "medium",
            "description": (
                "DiagnosisPage analysis history is React state only; logout/refresh clears history "
                "even though backend incidents/analyses persist."
            ),
            "expected": "History reloadable from API after refresh/login",
            "actual": "Local-only history array",
            "status": "open_candidate",
        }
    )

    report["summary"] = {
        "journey_ok": all(s.get("ok") for s in report["journey"]),
        "ai_pass": sum(1 for r in report["ai"] if r.get("ok")),
        "ai_total": len(report["ai"]),
        "error_cases_ok": all(e.get("ok") for e in report["errors"]),
    }
    (OUT / "phase5_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["journey_ok"] and report["summary"]["ai_pass"] == report["summary"]["ai_total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
