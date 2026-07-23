# DevGuard AI – API_SPECIFICATION.md

**Version:** 1.0  
**Status:** Proposed Baseline  
**API Style:** RESTful JSON API  
**Backend Framework:** FastAPI  
**Authentication:** JWT Bearer Tokens  
**Primary Domain:** AI-Powered Incident Intelligence Platform  

---

# 1. Purpose

This document defines the REST API specification for DevGuard AI.

The API supports the complete application flow:

```text
Authentication
    ↓
Projects
    ↓
Pipeline Runs
    ↓
Incidents
    ↓
File Upload
    ↓
AI Analysis
    ↓
Predictions
    ↓
Evidence
    ↓
Recommendations
    ↓
Resolution
    ↓
Reports
    ↓
Notifications
    ↓
History and Evaluation
```

The specification is intended to guide:

- FastAPI backend implementation
- React frontend integration
- Automated API testing
- OpenAPI documentation
- Future external integrations

---

# 2. API Conventions

## 2.1 Base URL

```text
/api/v1
```

Example:

```text
http://localhost:8000/api/v1/projects
```

---

## 2.2 Content Type

Standard requests and responses use:

```http
Content-Type: application/json
```

File uploads use:

```http
Content-Type: multipart/form-data
```

---

## 2.3 Authentication Header

Protected endpoints require:

```http
Authorization: Bearer <access_token>
```

---

## 2.4 Date and Time Format

All timestamps use ISO 8601 with timezone information.

Example:

```text
2026-07-19T08:30:00+05:30
```

---

## 2.5 Identifier Format

Primary identifiers use UUIDs.

Example:

```text
2f4805e2-26f6-41f3-b0f7-a98f38bbf421
```

Incidents also include a human-readable number:

```text
INC-000145
```

---

## 2.6 Pagination

List endpoints should support:

```text
page
page_size
```

Example:

```http
GET /api/v1/incidents?page=1&page_size=20
```

Recommended maximum:

```text
page_size = 100
```

Response:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total_items": 0,
  "total_pages": 0
}
```

---

## 2.7 Sorting

List endpoints may support:

```text
sort_by
sort_order
```

Example:

```http
GET /api/v1/incidents?sort_by=detected_at&sort_order=desc
```

Allowed sort order values:

- asc
- desc

---

## 2.8 Filtering

Filters should use query parameters.

Example:

```http
GET /api/v1/incidents?status=open&severity=critical&project_id=<uuid>
```

---

## 2.9 Standard Success Response

Single-resource endpoints return the resource directly.

Example:

```json
{
  "id": "2f4805e2-26f6-41f3-b0f7-a98f38bbf421",
  "name": "DevGuard API"
}
```

Action endpoints may return:

```json
{
  "success": true,
  "message": "Incident marked as resolved."
}
```

---

## 2.10 Standard Error Response

```json
{
  "error": {
    "code": "INCIDENT_NOT_FOUND",
    "message": "The requested incident could not be found.",
    "details": null,
    "request_id": "req-8e4cb012"
  }
}
```

Validation error:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request contains invalid values.",
    "details": [
      {
        "field": "email",
        "message": "A valid email address is required."
      }
    ],
    "request_id": "req-8e4cb012"
  }
}
```

---

# 3. HTTP Status Codes

| Code | Meaning |
|---|---|
| 200 | Request completed successfully |
| 201 | Resource created successfully |
| 202 | Request accepted for asynchronous processing |
| 204 | Request completed with no response body |
| 400 | Invalid request |
| 401 | Authentication required or invalid |
| 403 | User does not have permission |
| 404 | Resource not found |
| 409 | Conflict or duplicate resource |
| 413 | Uploaded file is too large |
| 415 | Unsupported file type |
| 422 | Validation error |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 502 | External AI provider error |
| 503 | Service temporarily unavailable |

---

# 4. Authentication API

## 4.1 Register User

```http
POST /auth/register
```

### Authentication

Public.

### Request

```json
{
  "email": "engineer@example.com",
  "password": "SecurePassword123!",
  "full_name": "DevOps Engineer"
}
```

### Response — 201

```json
{
  "id": "user-uuid",
  "email": "engineer@example.com",
  "full_name": "DevOps Engineer",
  "role": "engineer",
  "is_active": true,
  "created_at": "2026-07-19T08:30:00+05:30"
}
```

### Errors

- EMAIL_ALREADY_EXISTS
- WEAK_PASSWORD
- VALIDATION_ERROR

---

## 4.2 Login

```http
POST /auth/login
```

### Authentication

Public.

### Request

```json
{
  "email": "engineer@example.com",
  "password": "SecurePassword123!"
}
```

### Response — 200

```json
{
  "access_token": "jwt-access-token",
  "refresh_token": "jwt-refresh-token",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "user-uuid",
    "email": "engineer@example.com",
    "full_name": "DevOps Engineer",
    "role": "engineer"
  }
}
```

### Errors

- INVALID_CREDENTIALS
- USER_DISABLED

---

## 4.3 Refresh Access Token

```http
POST /auth/refresh
```

### Request

```json
{
  "refresh_token": "jwt-refresh-token"
}
```

### Response — 200

```json
{
  "access_token": "new-access-token",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## 4.4 Logout

```http
POST /auth/logout
```

### Authentication

Required.

### Request

```json
{
  "refresh_token": "jwt-refresh-token"
}
```

### Response — 200

```json
{
  "success": true,
  "message": "Logged out successfully."
}
```

---

## 4.5 Get Current User

```http
GET /auth/me
```

### Authentication

Required.

### Response — 200

```json
{
  "id": "user-uuid",
  "email": "engineer@example.com",
  "full_name": "DevOps Engineer",
  "avatar_url": null,
  "role": "engineer",
  "is_active": true,
  "last_login_at": "2026-07-19T08:30:00+05:30"
}
```

---

# 5. User Profile API

## 5.1 Update Current User

```http
PATCH /users/me
```

### Request

```json
{
  "full_name": "Senior DevOps Engineer",
  "avatar_url": "https://example.com/avatar.png"
}
```

### Response — 200

Returns the updated user.

---

## 5.2 Change Password

```http
POST /users/me/change-password
```

### Request

```json
{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword123!"
}
```

### Response — 200

```json
{
  "success": true,
  "message": "Password changed successfully."
}
```

---

# 6. Project API

## 6.1 Create Project

```http
POST /projects
```

### Authentication

Required.

### Request

```json
{
  "name": "Customer Portal",
  "key": "CP",
  "description": "Frontend and backend deployment project.",
  "repository_url": "https://github.com/example/customer-portal",
  "default_branch": "main",
  "ci_provider": "github_actions",
  "cloud_provider": "aws",
  "default_environment": "production"
}
```

### Response — 201

```json
{
  "id": "project-uuid",
  "name": "Customer Portal",
  "key": "CP",
  "description": "Frontend and backend deployment project.",
  "repository_url": "https://github.com/example/customer-portal",
  "default_branch": "main",
  "ci_provider": "github_actions",
  "cloud_provider": "aws",
  "default_environment": "production",
  "status": "active",
  "created_at": "2026-07-19T08:30:00+05:30"
}
```

---

## 6.2 List Projects

```http
GET /projects
```

### Query Parameters

- status
- ci_provider
- cloud_provider
- search
- page
- page_size
- sort_by
- sort_order

### Response — 200

```json
{
  "items": [
    {
      "id": "project-uuid",
      "name": "Customer Portal",
      "key": "CP",
      "ci_provider": "github_actions",
      "cloud_provider": "aws",
      "status": "active",
      "open_incident_count": 3,
      "last_pipeline_run_at": "2026-07-19T07:20:00+05:30"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total_items": 1,
  "total_pages": 1
}
```

---

## 6.3 Get Project

```http
GET /projects/{project_id}
```

### Response — 200

```json
{
  "id": "project-uuid",
  "name": "Customer Portal",
  "key": "CP",
  "description": "Frontend and backend deployment project.",
  "repository_url": "https://github.com/example/customer-portal",
  "default_branch": "main",
  "ci_provider": "github_actions",
  "cloud_provider": "aws",
  "default_environment": "production",
  "status": "active",
  "statistics": {
    "total_pipeline_runs": 81,
    "failed_pipeline_runs": 14,
    "open_incidents": 3,
    "resolved_incidents": 11
  },
  "created_at": "2026-07-19T08:30:00+05:30",
  "updated_at": "2026-07-19T08:30:00+05:30"
}
```

---

## 6.4 Update Project

```http
PATCH /projects/{project_id}
```

### Request

```json
{
  "description": "Updated project description.",
  "default_environment": "staging"
}
```

### Response — 200

Returns the updated project.

---

## 6.5 Archive Project

```http
POST /projects/{project_id}/archive
```

### Response — 200

```json
{
  "success": true,
  "message": "Project archived successfully."
}
```

---

## 6.6 Restore Project

```http
POST /projects/{project_id}/restore
```

### Response — 200

```json
{
  "success": true,
  "message": "Project restored successfully."
}
```

---

# 7. Pipeline Run API

## 7.1 Create Pipeline Run

```http
POST /projects/{project_id}/pipeline-runs
```

### Request

```json
{
  "external_run_id": "485",
  "provider": "github_actions",
  "workflow_name": "Production Deployment",
  "branch": "main",
  "commit_sha": "b04a77e",
  "triggered_by": "chanuka",
  "environment": "production",
  "status": "failed",
  "started_at": "2026-07-19T07:00:00+05:30",
  "completed_at": "2026-07-19T07:04:30+05:30",
  "source_url": "https://github.com/example/repository/actions/runs/485",
  "raw_metadata": {
    "job": "deploy-production"
  }
}
```

### Response — 201

Returns the created pipeline run.

---

## 7.2 List Pipeline Runs

```http
GET /projects/{project_id}/pipeline-runs
```

### Query Parameters

- status
- provider
- environment
- branch
- date_from
- date_to
- page
- page_size

---

## 7.3 Get Pipeline Run

```http
GET /pipeline-runs/{pipeline_run_id}
```

### Response — 200

```json
{
  "id": "pipeline-run-uuid",
  "project_id": "project-uuid",
  "external_run_id": "485",
  "provider": "github_actions",
  "workflow_name": "Production Deployment",
  "branch": "main",
  "commit_sha": "b04a77e",
  "environment": "production",
  "status": "failed",
  "duration_seconds": 270,
  "incident_count": 1,
  "source_url": "https://github.com/example/repository/actions/runs/485"
}
```

---

# 8. Incident API

## 8.1 Create Incident

```http
POST /incidents
```

### Request

```json
{
  "project_id": "project-uuid",
  "pipeline_run_id": "pipeline-run-uuid",
  "title": "Production deployment failed",
  "description": "GitHub Actions deployment failed during the ECS update step.",
  "source": "manual_upload",
  "severity": "critical",
  "priority": "urgent",
  "environment": "production"
}
```

### Response — 201

```json
{
  "id": "incident-uuid",
  "incident_number": "INC-000145",
  "project_id": "project-uuid",
  "pipeline_run_id": "pipeline-run-uuid",
  "title": "Production deployment failed",
  "status": "detected",
  "severity": "critical",
  "priority": "urgent",
  "environment": "production",
  "detected_at": "2026-07-19T08:30:00+05:30",
  "created_at": "2026-07-19T08:30:00+05:30"
}
```

---

## 8.2 List Incidents

```http
GET /incidents
```

### Query Parameters

- project_id
- pipeline_run_id
- status
- severity
- priority
- environment
- assignee_id
- category
- source
- date_from
- date_to
- search
- page
- page_size
- sort_by
- sort_order

### Response — 200

```json
{
  "items": [
    {
      "id": "incident-uuid",
      "incident_number": "INC-000145",
      "title": "Production deployment failed",
      "project": {
        "id": "project-uuid",
        "name": "Customer Portal"
      },
      "severity": "critical",
      "status": "open",
      "environment": "production",
      "predicted_category": "authorization_failure",
      "ai_confidence": 0.94,
      "detected_at": "2026-07-19T08:30:00+05:30",
      "current_assignee": null
    }
  ],
  "page": 1,
  "page_size": 20,
  "total_items": 1,
  "total_pages": 1
}
```

---

## 8.3 Get Incident Details

```http
GET /incidents/{incident_id}
```

### Response — 200

```json
{
  "id": "incident-uuid",
  "incident_number": "INC-000145",
  "title": "Production deployment failed",
  "description": "GitHub Actions deployment failed during the ECS update step.",
  "source": "manual_upload",
  "status": "open",
  "severity": "critical",
  "priority": "urgent",
  "environment": "production",
  "detected_at": "2026-07-19T08:30:00+05:30",
  "acknowledged_at": "2026-07-19T08:32:00+05:30",
  "resolved_at": null,
  "project": {
    "id": "project-uuid",
    "name": "Customer Portal",
    "key": "CP"
  },
  "pipeline_run": {
    "id": "pipeline-run-uuid",
    "external_run_id": "485",
    "provider": "github_actions",
    "workflow_name": "Production Deployment",
    "source_url": "https://github.com/example/repository/actions/runs/485"
  },
  "latest_analysis": {
    "id": "analysis-run-uuid",
    "status": "completed",
    "classification": {
      "category": "authorization_failure",
      "confidence": 0.94
    },
    "root_cause_summary": "The deployment role lacks permission to update the ECS service."
  },
  "current_assignee": null,
  "tags": [
    "aws",
    "ecs",
    "production"
  ]
}
```

---

## 8.4 Update Incident

```http
PATCH /incidents/{incident_id}
```

### Request

```json
{
  "title": "Production ECS deployment failed",
  "severity": "high",
  "priority": "high",
  "tags": [
    "aws",
    "ecs"
  ]
}
```

---

## 8.5 Change Incident Status

```http
POST /incidents/{incident_id}/status
```

### Request

```json
{
  "status": "in_progress",
  "comment": "Investigation started."
}
```

### Allowed Status Values

- detected
- analysing
- open
- in_progress
- resolved
- closed
- reopened
- ignored
- false_positive
- analysis_failed

### Response — 200

Returns the updated incident.

---

## 8.6 Assign Incident

```http
POST /incidents/{incident_id}/assign
```

### Request

```json
{
  "user_id": "user-uuid",
  "reason": "Assigned to the engineer responsible for AWS deployment."
}
```

---

## 8.7 Unassign Incident

```http
POST /incidents/{incident_id}/unassign
```

### Response — 200

```json
{
  "success": true,
  "message": "Incident unassigned successfully."
}
```

---

## 8.8 Acknowledge Incident

```http
POST /incidents/{incident_id}/acknowledge
```

### Response — 200

```json
{
  "success": true,
  "acknowledged_at": "2026-07-19T08:32:00+05:30"
}
```

---

# 9. File Upload API

## 9.1 Upload Incident Files

```http
POST /incidents/{incident_id}/files
```

### Content Type

```text
multipart/form-data
```

### Form Fields

- files: one or more files
- file_category: optional
- description: optional

### Supported Extensions

- log
- txt
- yaml
- yml
- json
- tf
- tfvars
- zip

### Response — 201

```json
{
  "files": [
    {
      "id": "file-uuid",
      "original_filename": "github-actions.log",
      "file_type": "log",
      "size_bytes": 204820,
      "checksum_sha256": "checksum",
      "validation_status": "valid",
      "secret_masking_status": "pending",
      "processing_status": "uploaded",
      "uploaded_at": "2026-07-19T08:35:00+05:30"
    }
  ]
}
```

### Errors

- FILE_TOO_LARGE
- UNSUPPORTED_FILE_TYPE
- EMPTY_FILE
- TOO_MANY_FILES
- INVALID_ARCHIVE
- DUPLICATE_FILE

---

## 9.2 List Incident Files

```http
GET /incidents/{incident_id}/files
```

---

## 9.3 Get File Metadata

```http
GET /files/{file_id}
```

---

## 9.4 Delete File

```http
DELETE /files/{file_id}
```

### Rules

Deletion should only be allowed before analysis, unless administrative cleanup is explicitly permitted.

---

# 10. AI Analysis API

## 10.1 Start Full Analysis

```http
POST /incidents/{incident_id}/analyses
```

### Request

```json
{
  "analysis_type": "full",
  "file_ids": [
    "file-uuid-1",
    "file-uuid-2"
  ],
  "options": {
    "enable_rag": true,
    "generate_recommendations": true,
    "top_k_predictions": 3
  }
}
```

### Response — 202

```json
{
  "analysis_run_id": "analysis-run-uuid",
  "incident_id": "incident-uuid",
  "status": "queued",
  "progress_percentage": 0,
  "created_at": "2026-07-19T08:36:00+05:30"
}
```

---

## 10.2 Reanalyse Incident

```http
POST /incidents/{incident_id}/reanalyse
```

### Request

```json
{
  "reason": "Additional Terraform file uploaded.",
  "file_ids": [
    "file-uuid-1",
    "file-uuid-2",
    "file-uuid-3"
  ]
}
```

### Response — 202

Returns the new analysis run.

---

## 10.3 Get Analysis Status

```http
GET /analyses/{analysis_run_id}/status
```

### Response — 200

```json
{
  "id": "analysis-run-uuid",
  "incident_id": "incident-uuid",
  "status": "retrieving",
  "current_stage": "documentation_retrieval",
  "progress_percentage": 72,
  "started_at": "2026-07-19T08:36:02+05:30",
  "estimated_remaining_seconds": 18,
  "stages": [
    {
      "name": "validation",
      "status": "completed",
      "duration_ms": 430
    },
    {
      "name": "secret_masking",
      "status": "completed",
      "duration_ms": 950
    },
    {
      "name": "classification",
      "status": "completed",
      "duration_ms": 180
    },
    {
      "name": "documentation_retrieval",
      "status": "running",
      "duration_ms": null
    }
  ]
}
```

---

## 10.4 Get Analysis Result

```http
GET /analyses/{analysis_run_id}
```

### Response — 200

```json
{
  "id": "analysis-run-uuid",
  "incident_id": "incident-uuid",
  "status": "completed",
  "analysis_type": "full",
  "duration_ms": 14850,
  "classification": {
    "primary": {
      "category": "authorization_failure",
      "confidence": 0.94,
      "rank": 1
    },
    "alternatives": [
      {
        "category": "authentication_failure",
        "confidence": 0.04,
        "rank": 2
      }
    ]
  },
  "root_cause": {
    "summary": "The deployment role lacked permission to update the ECS service.",
    "technical_explanation": "The workflow authenticated to AWS successfully, but the ECS UpdateService call was rejected by IAM.",
    "impact": "The new application version was not deployed to production.",
    "confidence": 0.93
  },
  "evidence_count": 3,
  "recommendation_count": 5,
  "retrieved_document_count": 4,
  "model_versions": {
    "classifier": "logreg-1.0.0",
    "embedding": "all-MiniLM-L6-v2",
    "reasoning": "provider-model-version"
  },
  "completed_at": "2026-07-19T08:36:17+05:30"
}
```

---

## 10.5 Cancel Analysis

```http
POST /analyses/{analysis_run_id}/cancel
```

### Rules

Cancellation is allowed only while the analysis is:

- queued
- validating
- preprocessing

Cancellation may be rejected after external LLM reasoning has started.

---

## 10.6 List Incident Analyses

```http
GET /incidents/{incident_id}/analyses
```

### Response

Returns all analysis runs in descending creation order.

---

# 11. Prediction API

## 11.1 List Analysis Predictions

```http
GET /analyses/{analysis_run_id}/predictions
```

### Response — 200

```json
{
  "items": [
    {
      "id": "prediction-uuid",
      "category": {
        "code": "authorization_failure",
        "name": "Authorization Failure"
      },
      "confidence": 0.94,
      "rank": 1,
      "root_cause_summary": "The AWS deployment role lacks ECS permissions.",
      "technical_explanation": "The request was authenticated but not authorized.",
      "model_version": "logreg-1.0.0"
    }
  ]
}
```

---

## 11.2 Get Prediction

```http
GET /predictions/{prediction_id}
```

---

# 12. Evidence API

## 12.1 List Analysis Evidence

```http
GET /analyses/{analysis_run_id}/evidence
```

### Query Parameters

- evidence_type
- min_importance
- file_id
- page
- page_size

### Response — 200

```json
{
  "items": [
    {
      "id": "evidence-uuid",
      "evidence_type": "permission_error",
      "source_file": {
        "id": "file-uuid",
        "name": "github-actions.log"
      },
      "line_start": 443,
      "line_end": 449,
      "importance_score": 0.96,
      "excerpt": "AccessDenied: not authorized to perform ecs:UpdateService",
      "explanation": "This line directly identifies the missing AWS permission."
    }
  ],
  "page": 1,
  "page_size": 20,
  "total_items": 1,
  "total_pages": 1
}
```

---

## 12.2 Get Evidence Item

```http
GET /evidence/{evidence_id}
```

### Response — 200

```json
{
  "id": "evidence-uuid",
  "analysis_run_id": "analysis-run-uuid",
  "prediction_id": "prediction-uuid",
  "evidence_type": "permission_error",
  "source_name": "github-actions.log",
  "line_start": 443,
  "line_end": 449,
  "raw_excerpt": "AccessDenied: not authorized to perform ecs:UpdateService",
  "normalized_excerpt": "accessdenied not authorized to perform ecs updateservice",
  "importance_score": 0.96,
  "explanation": "This line directly identifies the denied AWS operation.",
  "surrounding_context": {
    "before": [
      "Running deployment command..."
    ],
    "after": [
      "Process completed with exit code 1."
    ]
  }
}
```

---

# 13. Retrieved Documentation API

## 13.1 List Retrieved Sources

```http
GET /analyses/{analysis_run_id}/sources
```

### Response — 200

```json
{
  "items": [
    {
      "id": "retrieval-record-uuid",
      "rank": 1,
      "similarity_score": 0.892341,
      "used_in_reasoning": true,
      "document": {
        "title": "Amazon ECS API Permissions",
        "provider": "aws",
        "source_url": "https://docs.aws.amazon.com/..."
      },
      "chunk": {
        "heading": "UpdateService permissions",
        "content_preview": "The caller must have permission to update the ECS service..."
      }
    }
  ]
}
```

---

# 14. Recommendation API

## 14.1 List Analysis Recommendations

```http
GET /analyses/{analysis_run_id}/recommendations
```

### Response — 200

```json
{
  "items": [
    {
      "id": "recommendation-uuid",
      "step_number": 1,
      "title": "Update the deployment IAM role",
      "action": "Add ecs:UpdateService permission for the target ECS service.",
      "explanation": "The evidence shows AWS rejected this operation.",
      "expected_result": "The workflow can update the ECS service.",
      "risk_level": "medium",
      "difficulty": "moderate",
      "prevention_type": "immediate_fix",
      "accepted": null,
      "completed": false
    }
  ]
}
```

---

## 14.2 Update Recommendation State

```http
PATCH /recommendations/{recommendation_id}
```

### Request

```json
{
  "accepted": true,
  "completed": true
}
```

---

## 14.3 Regenerate Recommendations

```http
POST /analyses/{analysis_run_id}/recommendations/regenerate
```

### Request

```json
{
  "reason": "Generate less risky remediation steps.",
  "include_prevention": true
}
```

### Response — 202

```json
{
  "success": true,
  "message": "Recommendation regeneration started."
}
```

---

# 15. Incident Notes API

## 15.1 Add Incident Note

```http
POST /incidents/{incident_id}/notes
```

### Request

```json
{
  "note_type": "investigation",
  "content": "Confirmed that the role is missing ecs:UpdateService.",
  "is_pinned": false
}
```

### Response — 201

Returns the created note.

---

## 15.2 List Incident Notes

```http
GET /incidents/{incident_id}/notes
```

---

## 15.3 Update Incident Note

```http
PATCH /notes/{note_id}
```

---

## 15.4 Delete Incident Note

```http
DELETE /notes/{note_id}
```

Only the author or an administrator should be allowed to delete a note.

---

# 16. Incident Timeline API

## 16.1 Get Incident Timeline

```http
GET /incidents/{incident_id}/timeline
```

### Response — 200

```json
{
  "items": [
    {
      "id": "event-uuid",
      "event_type": "incident_created",
      "actor_type": "system",
      "title": "Incident created",
      "description": "A failed pipeline run created this incident.",
      "occurred_at": "2026-07-19T08:30:00+05:30"
    },
    {
      "id": "event-uuid-2",
      "event_type": "analysis_completed",
      "actor_type": "ai",
      "title": "AI analysis completed",
      "description": "Authorization failure detected with 94% confidence.",
      "occurred_at": "2026-07-19T08:36:17+05:30"
    }
  ]
}
```

---

# 17. Resolution API

## 17.1 Resolve Incident

```http
POST /incidents/{incident_id}/resolve
```

### Request

```json
{
  "resolution_summary": "Updated the IAM policy and reran the workflow successfully.",
  "confirmed_root_cause": "The deployment role lacked ecs:UpdateService permission.",
  "resolution_steps": [
    "Reviewed the deployment role.",
    "Added the required ECS permission.",
    "Reran the GitHub Actions workflow."
  ],
  "prevention_actions": [
    "Add an IAM permission validation step before deployment."
  ],
  "time_spent_minutes": 18,
  "ai_recommendation_used": true
}
```

### Response — 200

```json
{
  "incident_id": "incident-uuid",
  "status": "resolved",
  "resolved_at": "2026-07-19T08:55:00+05:30",
  "resolution": {
    "id": "resolution-uuid",
    "resolution_summary": "Updated the IAM policy and reran the workflow successfully.",
    "time_spent_minutes": 18,
    "ai_recommendation_used": true
  }
}
```

---

## 17.2 Reopen Incident

```http
POST /incidents/{incident_id}/reopen
```

### Request

```json
{
  "reason": "The same deployment failure occurred again."
}
```

---

## 17.3 List Incident Resolutions

```http
GET /incidents/{incident_id}/resolutions
```

---

# 18. Report API

## 18.1 Generate Incident Report

```http
POST /incidents/{incident_id}/reports
```

### Request

```json
{
  "format": "pdf",
  "include_evidence": true,
  "include_recommendations": true,
  "include_timeline": true,
  "include_resolution": true
}
```

### Response — 202

```json
{
  "report_id": "report-uuid",
  "incident_id": "incident-uuid",
  "format": "pdf",
  "generation_status": "queued"
}
```

---

## 18.2 List Incident Reports

```http
GET /incidents/{incident_id}/reports
```

---

## 18.3 Get Report Metadata

```http
GET /reports/{report_id}
```

### Response — 200

```json
{
  "id": "report-uuid",
  "incident_id": "incident-uuid",
  "format": "pdf",
  "version": 1,
  "generation_status": "completed",
  "created_at": "2026-07-19T09:00:00+05:30",
  "download_url": "/api/v1/reports/report-uuid/download"
}
```

---

## 18.4 Download Report

```http
GET /reports/{report_id}/download
```

### Response

Returns the generated report file.

---

## 18.5 Regenerate Report

```http
POST /reports/{report_id}/regenerate
```

---

# 19. Notification API

## 19.1 List Notifications

```http
GET /notifications
```

### Query Parameters

- is_read
- severity
- notification_type
- incident_id
- page
- page_size

### Response — 200

```json
{
  "items": [
    {
      "id": "notification-uuid",
      "notification_type": "analysis_complete",
      "title": "AI analysis completed",
      "message": "Incident INC-000145 was classified as an authorization failure.",
      "severity": "critical",
      "channel": "in_app",
      "delivery_status": "sent",
      "is_read": false,
      "incident_id": "incident-uuid",
      "created_at": "2026-07-19T08:36:18+05:30"
    }
  ],
  "unread_count": 1,
  "page": 1,
  "page_size": 20,
  "total_items": 1,
  "total_pages": 1
}
```

---

## 19.2 Mark Notification as Read

```http
POST /notifications/{notification_id}/read
```

---

## 19.3 Mark All Notifications as Read

```http
POST /notifications/read-all
```

---

## 19.4 Delete Notification

```http
DELETE /notifications/{notification_id}
```

---

# 20. Dashboard API

## 20.1 Get Dashboard Summary

```http
GET /dashboard/summary
```

### Query Parameters

- project_id
- date_from
- date_to

### Response — 200

```json
{
  "open_incidents": 8,
  "critical_incidents": 2,
  "active_analyses": 1,
  "successful_deployments": 74,
  "failed_deployments": 12,
  "average_resolution_minutes": 26.4,
  "deployment_success_rate": 86.05
}
```

---

## 20.2 Get Incident Trend

```http
GET /dashboard/incident-trend
```

### Query Parameters

- project_id
- interval: day, week, month
- date_from
- date_to

### Response — 200

```json
{
  "interval": "day",
  "items": [
    {
      "period": "2026-07-18",
      "incident_count": 4,
      "resolved_count": 3
    },
    {
      "period": "2026-07-19",
      "incident_count": 2,
      "resolved_count": 1
    }
  ]
}
```

---

## 20.3 Get Severity Distribution

```http
GET /dashboard/severity-distribution
```

### Response — 200

```json
{
  "critical": 2,
  "high": 4,
  "medium": 8,
  "low": 3
}
```

---

## 20.4 Get Failure Category Distribution

```http
GET /dashboard/failure-categories
```

### Response — 200

```json
{
  "items": [
    {
      "category": "authorization_failure",
      "count": 7
    },
    {
      "category": "dependency_failure",
      "count": 5
    }
  ]
}
```

---

## 20.5 Get Recent Incidents

```http
GET /dashboard/recent-incidents
```

### Query Parameters

- limit

---

# 21. History API

History should be derived from incidents and analysis runs.

## 21.1 Search Incident History

```http
GET /history/incidents
```

### Query Parameters

- search
- project_id
- provider
- category
- severity
- status
- environment
- resolved_by
- date_from
- date_to
- page
- page_size

### Response

Returns historical incidents with resolution and AI summary fields.

---

## 21.2 Export Incident History

```http
POST /history/incidents/export
```

### Request

```json
{
  "format": "csv",
  "filters": {
    "project_id": "project-uuid",
    "date_from": "2026-07-01",
    "date_to": "2026-07-31"
  }
}
```

### Response — 202

Returns export job metadata.

---

# 22. Feedback API

## 22.1 Submit AI Feedback

```http
POST /feedback
```

### Request

```json
{
  "incident_id": "incident-uuid",
  "analysis_run_id": "analysis-run-uuid",
  "prediction_id": "prediction-uuid",
  "feedback_type": "classification",
  "rating": 5,
  "is_correct": true,
  "is_useful": true,
  "comment": "The category and explanation were correct."
}
```

### Response — 201

Returns the created feedback.

---

## 22.2 Submit Recommendation Feedback

```http
POST /recommendations/{recommendation_id}/feedback
```

### Request

```json
{
  "rating": 4,
  "is_useful": true,
  "comment": "The recommendation worked after adjusting the resource scope."
}
```

---

# 23. Failure Category API

## 23.1 List Failure Categories

```http
GET /failure-categories
```

### Response — 200

```json
{
  "items": [
    {
      "id": "category-uuid",
      "code": "authorization_failure",
      "name": "Authorization Failure",
      "description": "A request was authenticated but lacked permission.",
      "default_severity": "high",
      "is_active": true
    }
  ]
}
```

---

# 24. Model and Evaluation API

These endpoints are primarily for administrators and research evaluation.

## 24.1 List Model Versions

```http
GET /admin/models
```

---

## 24.2 Get Model Version

```http
GET /admin/models/{model_version_id}
```

---

## 24.3 Activate Model Version

```http
POST /admin/models/{model_version_id}/activate
```

### Request

```json
{
  "model_type": "classifier"
}
```

---

## 24.4 List Evaluation Results

```http
GET /admin/evaluations
```

### Query Parameters

- model_version_id
- evaluation_type
- metric_name
- dataset_version

---

## 24.5 Create Evaluation Record

```http
POST /admin/evaluations
```

### Request

```json
{
  "model_version_id": "model-version-uuid",
  "evaluation_type": "classification",
  "dataset_version": "dataset-v1",
  "metric_name": "macro_f1",
  "metric_value": 0.8732,
  "sample_size": 1200,
  "metadata": {
    "split": "test"
  }
}
```

---

# 25. Administration API

## 25.1 List Users

```http
GET /admin/users
```

### Query Parameters

- role
- is_active
- search
- page
- page_size

---

## 25.2 Get User

```http
GET /admin/users/{user_id}
```

---

## 25.3 Update User Role

```http
PATCH /admin/users/{user_id}/role
```

### Request

```json
{
  "role": "admin"
}
```

---

## 25.4 Disable User

```http
POST /admin/users/{user_id}/disable
```

---

## 25.5 Enable User

```http
POST /admin/users/{user_id}/enable
```

---

## 25.6 Get Audit Logs

```http
GET /admin/audit-logs
```

### Query Parameters

- user_id
- action
- resource_type
- resource_id
- date_from
- date_to
- page
- page_size

---

# 26. Settings API

## 26.1 Get User Settings

```http
GET /settings
```

### Response — 200

```json
{
  "theme": "dark",
  "language": "en",
  "timezone": "Asia/Colombo",
  "notifications": {
    "in_app": true,
    "email": false
  },
  "ai": {
    "confidence_threshold": 0.65,
    "enable_rag": true
  }
}
```

---

## 26.2 Update User Settings

```http
PATCH /settings
```

### Request

```json
{
  "theme": "dark",
  "timezone": "Asia/Colombo",
  "notifications": {
    "in_app": true
  }
}
```

---

# 27. Health and System API

## 27.1 Basic Health Check

```http
GET /health
```

### Response — 200

```json
{
  "name": "DevGuard AI API",
  "version": "1.0.0",
  "status": "running"
}
```

---

## 27.2 Readiness Check

```http
GET /health/ready
```

### Response — 200

```json
{
  "status": "ready",
  "dependencies": {
    "database": "available",
    "vector_store": "available",
    "classifier": "loaded",
    "llm_provider": "available"
  }
}
```

---

## 27.3 Liveness Check

```http
GET /health/live
```

### Response — 200

```json
{
  "status": "alive"
}
```

---

# 28. Webhook API — Future Scope

## 28.1 GitHub Actions Webhook

```http
POST /webhooks/github
```

### Behaviour

1. Validate GitHub signature.
2. Parse workflow event.
3. Create or update the pipeline run.
4. Create an incident when the run fails.
5. Store relevant logs or fetch them through the integration.
6. Start AI analysis.
7. Notify users.

### Security

Use:

```text
X-Hub-Signature-256
```

Webhook endpoints must not use normal user JWT authentication.

---

# 29. Idempotency

Create and action endpoints should support an optional header:

```http
Idempotency-Key: unique-client-generated-key
```

Recommended for:

- Incident creation
- Analysis creation
- Report generation
- Webhook processing
- Resolution submission

Duplicate requests with the same key should return the original result.

---

# 30. Rate Limiting

Suggested MVP limits:

| Endpoint Type | Suggested Limit |
|---|---|
| Authentication | 10 requests per minute |
| General API | 120 requests per minute |
| File Upload | 20 requests per hour |
| AI Analysis | 10 analyses per hour |
| Report Generation | 20 requests per hour |

Limits should be configurable.

---

# 31. Permission Model

## Viewer

Can:

- View projects
- View incidents
- View analyses
- View reports
- View notifications

Cannot:

- Create projects
- Upload files
- Start analyses
- Resolve incidents
- Manage users

## Engineer

Can:

- Create and update projects
- Create incidents
- Upload files
- Start analyses
- Add notes
- Assign incidents
- Resolve incidents
- Generate reports
- Submit feedback

## Admin

Can perform all engineer actions plus:

- Manage users
- Manage model versions
- View audit logs
- Configure organization settings
- Archive projects
- Access evaluation endpoints

---

# 32. Pydantic Schema Recommendations

Recommended schema grouping:

```text
schemas/
├── auth.py
├── user.py
├── project.py
├── pipeline_run.py
├── incident.py
├── uploaded_file.py
├── analysis.py
├── prediction.py
├── evidence.py
├── recommendation.py
├── resolution.py
├── report.py
├── notification.py
├── feedback.py
├── dashboard.py
├── pagination.py
└── error.py
```

Use separate schemas for:

- Create
- Update
- Response
- List item
- Detailed response

Example:

```text
IncidentCreate
IncidentUpdate
IncidentListItem
IncidentDetailResponse
IncidentStatusUpdate
```

---

# 33. FastAPI Router Structure

```text
api/
└── v1/
    ├── router.py
    └── endpoints/
        ├── auth.py
        ├── users.py
        ├── projects.py
        ├── pipeline_runs.py
        ├── incidents.py
        ├── files.py
        ├── analyses.py
        ├── predictions.py
        ├── evidence.py
        ├── recommendations.py
        ├── notes.py
        ├── resolutions.py
        ├── reports.py
        ├── notifications.py
        ├── dashboard.py
        ├── history.py
        ├── feedback.py
        ├── failure_categories.py
        ├── settings.py
        ├── admin.py
        ├── webhooks.py
        └── health.py
```

---

# 34. API Service Layer

API route handlers should remain thin.

Recommended flow:

```text
FastAPI Endpoint
    ↓
Application Service
    ↓
Domain Rules
    ↓
Repository
    ↓
Database or AI Service
```

Example:

```text
POST /incidents/{id}/analyses
    ↓
AnalysisApplicationService.start_analysis()
    ↓
Validate incident and files
    ↓
Create analysis_run
    ↓
Queue AnalysisOrchestrator
    ↓
Return 202 response
```

---

# 35. API Security Requirements

1. Validate every request through Pydantic.
2. Require JWT authentication for protected routes.
3. Apply role-based authorization.
4. Verify project ownership or organization access.
5. Never expose password hashes.
6. Never expose raw secrets from uploaded logs.
7. Sanitize stored and returned evidence.
8. Validate file content and size.
9. Protect report download endpoints.
10. Verify webhook signatures.
11. Log privileged actions.
12. Prevent mass assignment in update endpoints.
13. Use short-lived access tokens.
14. Rotate or revoke refresh tokens.
15. Return safe errors without stack traces.

---

# 36. Asynchronous Processing

The following endpoints should return `202 Accepted`:

- Start AI analysis
- Reanalyse incident
- Regenerate recommendations
- Generate report
- Export history
- Webhook-triggered analysis

The frontend should poll status endpoints initially.

Future improvement:

- Server-Sent Events
- WebSockets
- Push notifications

---

# 37. API Versioning

The first API version is:

```text
/api/v1
```

Breaking changes should introduce:

```text
/api/v2
```

Non-breaking additions may remain in v1.

Examples of breaking changes:

- Removing response fields
- Renaming fields
- Changing field types
- Changing endpoint behaviour
- Changing status code semantics

---

# 38. OpenAPI Documentation

FastAPI should expose:

```text
/docs
/redoc
/openapi.json
```

Production deployments may restrict or disable public access to API documentation.

Each endpoint should document:

- Summary
- Description
- Authentication
- Request schema
- Response schema
- Error responses
- Permission requirements

---

# 39. MVP Endpoint Priority

## Phase 1 — Foundation

- POST /auth/register
- POST /auth/login
- GET /auth/me
- GET /health
- GET /health/ready

## Phase 2 — Projects and Incidents

- POST /projects
- GET /projects
- GET /projects/{id}
- POST /incidents
- GET /incidents
- GET /incidents/{id}
- PATCH /incidents/{id}

## Phase 3 — Upload and Analysis

- POST /incidents/{id}/files
- GET /incidents/{id}/files
- POST /incidents/{id}/analyses
- GET /analyses/{id}/status
- GET /analyses/{id}

## Phase 4 — AI Results

- GET /analyses/{id}/predictions
- GET /analyses/{id}/evidence
- GET /analyses/{id}/sources
- GET /analyses/{id}/recommendations

## Phase 5 — Resolution and Reporting

- POST /incidents/{id}/resolve
- POST /incidents/{id}/reopen
- POST /incidents/{id}/reports
- GET /reports/{id}
- GET /reports/{id}/download

## Phase 6 — User Experience

- GET /dashboard/summary
- GET /dashboard/recent-incidents
- GET /notifications
- POST /notifications/{id}/read
- GET /history/incidents
- POST /feedback

---

# 40. Final API Flow

```text
POST /auth/login
        ↓
POST /projects
        ↓
POST /incidents
        ↓
POST /incidents/{id}/files
        ↓
POST /incidents/{id}/analyses
        ↓
GET /analyses/{id}/status
        ↓
GET /analyses/{id}
        ↓
GET /analyses/{id}/evidence
        ↓
GET /analyses/{id}/recommendations
        ↓
POST /incidents/{id}/resolve
        ↓
POST /incidents/{id}/reports
        ↓
GET /reports/{id}/download
```

---

# 41. Architecture Decision

DevGuard AI will expose a versioned REST API using FastAPI and JSON.

The API will be organized around:

- Projects
- Pipeline Runs
- Incidents
- Analysis Runs
- Evidence
- Recommendations
- Resolutions
- Reports
- Notifications

The incident remains the main business resource.

The analysis run remains the main AI execution resource.

This API specification should be treated as the baseline for backend and frontend implementation.
