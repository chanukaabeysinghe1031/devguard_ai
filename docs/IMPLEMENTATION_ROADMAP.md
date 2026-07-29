# DevGuard AI

# IMPLEMENTATION_ROADMAP.md

**Version:** 2.0  
**Status:** Active Development  
**Document Type:** Master Implementation Roadmap  
**Project Type:** MSc Dissertation + Commercial SaaS Platform  
**Last Updated:** July 2026

---

# Part 1 --- Vision, Principles and High-Level Roadmap

## 1. Introduction

### 1.1 Purpose

This document defines the official implementation roadmap for **DevGuard
AI**.

It specifies the complete development sequence required to build the
platform from an empty repository to a production-ready enterprise SaaS
application.

The roadmap ensures every component is implemented in the correct order
while maintaining a stable, modular, testable architecture.

This document serves as the primary execution guide throughout
development.

------------------------------------------------------------------------

### 1.2 Scope

This roadmap covers implementation of:

-   Project Foundation
-   Backend Services
-   Database
-   Authentication
-   User & Organization Management
-   Project Management
-   Incident Management
-   File Processing
-   Dataset Pipeline
-   Machine Learning
-   Evidence Extraction
-   Retrieval-Augmented Generation (RAG)
-   AI Reasoning
-   Recommendation Engine
-   Report Generation
-   Analytics Dashboard
-   Enterprise Frontend
-   Administration
-   Evaluation
-   Deployment

All previously approved architecture documents are considered part of
this implementation.

------------------------------------------------------------------------

# 2. Product Vision

DevGuard AI is an **AI-powered DevOps Incident Intelligence Platform**.

Instead of simply detecting CI/CD failures, DevGuard AI performs
intelligent investigations by:

-   Analysing CI/CD failures
-   Analysing Infrastructure-as-Code
-   Classifying failure categories
-   Extracting supporting evidence
-   Retrieving technical documentation using RAG
-   Performing LLM-based root cause reasoning
-   Generating explainable remediation recommendations
-   Managing the complete incident lifecycle
-   Producing investigation reports and analytics

The long-term vision is to evolve DevGuard AI into an enterprise AI
DevOps Copilot.

------------------------------------------------------------------------

# 3. Product Objectives

## Functional Objectives

-   Project Management
-   Incident Management
-   File Upload & Processing
-   CI/CD Log Parsing
-   Infrastructure-as-Code Parsing
-   Machine Learning Classification
-   Evidence Extraction
-   RAG Retrieval
-   AI Reasoning
-   Recommendation Generation
-   Report Generation
-   Analytics Dashboard
-   Evaluation Metrics
-   Administration

## Non-Functional Objectives

-   Scalable Architecture
-   High Performance
-   Explainable AI
-   Secure by Design
-   Cloud Ready
-   Testable
-   Extensible
-   Commercial SaaS Ready
-   Well Documented

------------------------------------------------------------------------

# 4. Development Philosophy

## Modular Development

Each module must:

-   Have a single responsibility
-   Be independently testable
-   Minimize coupling
-   Maximize reusability

## Incremental Delivery

Only one module should be actively developed at a time.

Every completed module must leave the system in a working state.

## Test-Driven Quality

Every module must include:

-   Unit Tests
-   Integration Tests
-   Validation Tests
-   API Tests (where applicable)

## Documentation-Driven Development

A module is **not complete** until its documentation has been updated.

## Architecture First

Implementation must follow:

-   PROJECT_CONSTITUTION.md
-   MASTER_ARCHITECTURE.md
-   DATABASE_ARCHITECTURE.md
-   AI_ARCHITECTURE.md
-   API_SPECIFICATION.md
-   DATASET_SPECIFICATION.md
-   UI_UX_DESIGN_SPECIFICATION.md

No implementation should diverge from the approved architecture without
review.

------------------------------------------------------------------------

# 5. Development Strategy

Every module follows the same workflow:

Planning

↓

Architecture Review

↓

Implementation

↓

Unit Testing

↓

Integration Testing

↓

Documentation

↓

Code Review

↓

Approval

↓

Next Module

No shortcuts are permitted.

------------------------------------------------------------------------

# 6. High-Level Development Phases

    Phase 1  Planning & Foundation
            ↓
    Phase 2  Core Platform
            ↓
    Phase 3  Business Domain
            ↓
    Phase 4  Dataset & Data Pipeline
            ↓
    Phase 5  Machine Learning
            ↓
    Phase 6  AI Intelligence Engine
            ↓
    Phase 7  Enterprise Frontend
            ↓
    Phase 8  Integration
            ↓
    Phase 9  Evaluation
            ↓
    Phase 10 Deployment
            ↓
    Phase 11 Commercial SaaS Expansion

------------------------------------------------------------------------

# 7. Phase Goals

  Phase   Goal
  ------- -------------------------------------------------------
  1       Create project foundation and development environment
  2       Build reusable backend platform and database
  3       Implement projects, incidents and file management
  4       Build labelled datasets and ingestion pipeline
  5       Train and evaluate ML models
  6       Build RAG, evidence extraction and AI reasoning
  7       Implement enterprise React frontend
  8       Connect frontend, backend and AI pipeline
  9       Benchmark and evaluate the platform
  10      Deploy using Docker, GitHub Actions and AWS
  11      Extend toward commercial SaaS capabilities

------------------------------------------------------------------------

# 8. Success Criteria

The project will be considered successful when:

-   Users can create Projects.
-   Users can create Incidents.
-   Pipeline logs and IaC files can be uploaded.
-   AI classifies failures.
-   Evidence is extracted.
-   Documentation is retrieved through RAG.
-   LLM produces explainable root-cause analysis.
-   Recommendations are generated.
-   Reports are produced.
-   Analytics dashboards display operational insights.
-   The system is fully documented and ready for MSc demonstration and
    future commercial development.

---

# Part 2 — Detailed Implementation Plan

## 1. Purpose of Part 2

Part 2 defines the detailed implementation sequence for the first major development stages of DevGuard AI.

It covers:

- Phase 1 — Planning and Foundation
- Phase 2 — Core Platform
- Phase 3 — Business Domain
- Database implementation order
- Authentication and authorization
- User and organization management
- Project management
- Incident management
- Pipeline runs
- File upload and validation
- Analysis-run orchestration
- Testing, documentation and quality gates

The purpose of this part is to provide a practical execution guide that can be followed module by module.

---

# 2. Mandatory Execution Rule

Modules must be completed sequentially.

The required workflow for every module is:

```text
Planning
    ↓
Architecture Review
    ↓
Implementation
    ↓
Unit Testing
    ↓
Integration Testing
    ↓
Documentation
    ↓
Code Review
    ↓
Approval
    ↓
Next Module
```

Do not begin a new module while the current module has unresolved critical defects.

---

# PHASE 1 — PLANNING AND FOUNDATION

## 3. Phase 1 Goal

Create a stable development environment and project structure that supports all later backend, frontend, AI and deployment modules.

## 3.1 Module 1.1 — Repository and Governance

### Goal

Create the official source repository and development rules.

### Tasks

- Create the Git repository.
- Add `.gitignore`.
- Add `README.md`.
- Add `LICENSE` if required.
- Add `CONTRIBUTING.md`.
- Add `PROJECT_CONSTITUTION.md`.
- Add branch protection guidance.
- Define pull-request template.
- Define issue templates.
- Define commit-message conventions.
- Create release-tagging convention.
- Add code-owner rules where appropriate.

### Git Branches

```text
main
develop
feature/*
fix/*
refactor/*
docs/*
release/*
```

### Commit Types

```text
feat:
fix:
refactor:
test:
docs:
chore:
perf:
ci:
```

### Definition of Done

- Repository is created.
- Development rules are documented.
- Pull-request workflow is defined.
- Initial commit is tagged.
- No secrets are committed.

---

## 3.2 Module 1.2 — Project Structure

### Goal

Create the approved monorepo structure.

### Recommended Structure

```text
devguard-ai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── application/
│   │   ├── core/
│   │   ├── domain/
│   │   ├── infrastructure/
│   │   ├── integrations/
│   │   ├── schemas/
│   │   └── main.py
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── stores/
│   │   ├── styles/
│   │   ├── types/
│   │   └── utils/
│   ├── package.json
│   └── Dockerfile
├── ai/
│   ├── datasets/
│   ├── experiments/
│   ├── models/
│   ├── notebooks/
│   ├── pipelines/
│   └── evaluation/
├── infrastructure/
│   ├── docker/
│   ├── terraform/
│   ├── monitoring/
│   └── scripts/
├── docs/
├── .github/
│   └── workflows/
├── docker-compose.yml
└── README.md
```

### Definition of Done

- All top-level folders exist.
- Folder responsibilities are documented.
- Empty folders contain placeholder files where required.
- Backend and frontend start from the approved locations.

---

## 3.3 Module 1.3 — Backend Skeleton

### Goal

Create the FastAPI backend foundation.

### Tasks

- Initialize Python project.
- Configure FastAPI.
- Create application factory or structured startup.
- Add API router.
- Add `/health`.
- Add `/health/live`.
- Add `/health/ready`.
- Configure CORS.
- Configure logging.
- Add request ID middleware.
- Add startup and shutdown hooks.
- Configure environment validation.
- Add base exception handling.
- Add initial tests.

### Definition of Done

- Backend starts locally.
- Swagger is available.
- Health endpoint returns HTTP 200.
- Structured logs are produced.
- Initial tests pass.

---

## 3.4 Module 1.4 — Frontend Skeleton

### Goal

Create the React frontend foundation.

### Tasks

- Initialize React with TypeScript.
- Configure routing.
- Configure environment variables.
- Add application shell.
- Add global styles.
- Add design tokens.
- Add API client foundation.
- Add error boundary.
- Add loading state.
- Add placeholder authentication routes.
- Configure linting and formatting.

### Initial Routes

```text
/login
/dashboard
/projects
/incidents
/settings
```

### Definition of Done

- Frontend starts locally.
- Routing works.
- Application shell renders.
- API client can call the backend health endpoint.
- Linting passes.

---

## 3.5 Module 1.5 — Docker Development Environment

### Goal

Create a reproducible local environment.

### Services

```text
frontend
backend
postgres
redis
```

A vector database may be added later during the RAG phase.

### Tasks

- Create backend Dockerfile.
- Create frontend Dockerfile.
- Create `docker-compose.yml`.
- Add PostgreSQL service.
- Add Redis service if required for queues or token management.
- Add named volumes.
- Add service health checks.
- Add dependency ordering.
- Document startup and shutdown commands.

### Required Commands

```bash
docker compose up --build
docker compose down
docker compose logs -f
docker compose ps
```

### Definition of Done

- All services start successfully.
- Backend connects to PostgreSQL.
- Frontend reaches backend.
- Containers restart correctly.
- Health checks pass.

---

## 3.6 Module 1.6 — Configuration and Secrets

### Goal

Centralize environment configuration securely.

### Tasks

- Create typed settings.
- Add `.env.example`.
- Separate development, test and production configuration.
- Validate required environment variables.
- Add secret-redaction rules.
- Prevent secrets from appearing in logs.
- Document every variable.
- Define future cloud secret-management strategy.

### Definition of Done

- Invalid configuration fails during startup.
- `.env.example` is complete.
- No real secrets exist in source control.
- Configuration documentation is complete.

---

## 3.7 Module 1.7 — Logging and Observability Foundation

### Goal

Create consistent operational visibility.

### Tasks

- Add structured application logging.
- Add log levels.
- Add request IDs.
- Log request method, route, status and duration.
- Add safe exception logging.
- Add redaction of passwords, tokens and secrets.
- Add initial metrics hooks.
- Define future monitoring integration points.

### Definition of Done

- Every request has a request ID.
- Errors are traceable.
- Sensitive data is excluded.
- Logs are readable in Docker.

---

## 3.8 Phase 1 Quality Gate

- [ ] Repository governance is complete.
- [ ] Folder structure is approved.
- [ ] Backend starts.
- [ ] Frontend starts.
- [ ] Docker Compose starts all required services.
- [ ] Health endpoints pass.
- [ ] PostgreSQL connection works.
- [ ] Environment validation works.
- [ ] Structured logging works.
- [ ] Unit tests pass.
- [ ] Setup documentation is complete.

---

# PHASE 2 — CORE PLATFORM

## 4. Phase 2 Goal

Build the secure and reusable platform required by all business and AI modules.

---

## 4.1 Module 2.1 — Database Foundation

### Tasks

- Configure SQLAlchemy.
- Create declarative base.
- Create database engine factory.
- Create session factory.
- Create request-scoped session dependency.
- Configure connection pooling.
- Configure transaction handling.
- Add test database.
- Extend readiness health check.

### Definition of Done

- Sessions open and close correctly.
- Failed transactions roll back.
- Test database is isolated.
- Database readiness is verified.

---

## 4.2 Module 2.2 — Core Enums

### Initial Enums

```text
UserRole
UserStatus
OrganizationRole
ProjectStatus
ProjectVisibility
PipelineProvider
PipelineRunStatus
IncidentStatus
IncidentSeverity
IncidentPriority
FileType
FileValidationStatus
AnalysisRunStatus
AnalysisStage
EvidenceType
RiskLevel
RecommendationStatus
ModelType
ModelStatus
FeedbackType
NotificationType
```

### Definition of Done

- Enums are stored consistently.
- Enum values are documented.
- Invalid values are rejected.

---

## 4.3 Module 2.3 — Core Database Models

### Required Models

```text
User
Organization
OrganizationMember
Project
ProjectIntegration
PipelineRun
Incident
UploadedFile
AnalysisRun
FailureCategory
Prediction
EvidenceItem
RetrievedDocument
Recommendation
IncidentEvent
IncidentNote
IncidentAssignment
IncidentResolution
IncidentReport
Notification
Feedback
ModelVersion
Evaluation
AnalysisHistory
AuditLog
```

### Common Fields

```text
id
created_at
updated_at
```

Organization-scoped entities should also include:

```text
organization_id
```

### Model Standards

- Use UUID primary keys.
- Use UTC timestamps.
- Add required indexes.
- Add uniqueness constraints.
- Define delete behaviour.
- Avoid unnecessary nullable fields.
- Use JSONB only for flexible structured data.
- Do not store important searchable data only in JSONB.

### Definition of Done

- Models match the approved ERD.
- Relationships are reviewed.
- Constraints are tested.
- Model tests pass.

---

## 4.4 Module 2.4 — Alembic Migrations

### Tasks

- Configure Alembic.
- Create initial schema migration.
- Review generated SQL.
- Add indexes and constraints.
- Create downgrade behaviour.
- Test clean migration.
- Test downgrade and re-upgrade.
- Add migrations to CI.

### Definition of Done

- An empty database can reach the latest schema.
- Migration history is version controlled.
- CI validates migrations.

---

## 4.5 Module 2.5 — Repository Layer

### Base Repository Operations

```text
get_by_id
list
create
update
delete
exists
count
```

### Specialized Repositories

```text
UserRepository
OrganizationRepository
ProjectRepository
PipelineRunRepository
IncidentRepository
UploadedFileRepository
AnalysisRunRepository
PredictionRepository
EvidenceRepository
RecommendationRepository
ReportRepository
NotificationRepository
EvaluationRepository
AuditLogRepository
```

### Rules

Repositories must:

- Perform persistence operations.
- Support filtering.
- Support sorting.
- Support pagination.
- Enforce organization scoping.

Repositories must not:

- Construct HTTP responses.
- Perform AI reasoning.
- Contain unrelated business workflows.

### Definition of Done

- Route handlers do not access database sessions directly.
- Repository tests pass.
- Organization scoping is verified.

---

## 4.6 Module 2.6 — Service Layer

### Initial Services

```text
AuthenticationService
UserService
OrganizationService
ProjectService
PipelineRunService
IncidentService
FileService
AnalysisService
ReportService
NotificationService
AuditService
```

### Domain Exceptions

```text
ResourceNotFoundError
ResourceConflictError
AuthenticationError
PermissionDeniedError
DomainValidationError
OrganizationAccessError
InvalidStateTransitionError
FileValidationError
AnalysisExecutionError
```

### Definition of Done

- Services enforce business rules.
- Routes remain thin.
- Transactions are managed consistently.
- Domain exceptions are tested.

---

## 4.7 Module 2.7 — Authentication

### Features

- Registration
- Login
- Access tokens
- Refresh tokens
- Token rotation
- Logout
- Current-user endpoint
- Password change
- Disabled-account protection

### Endpoints

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
POST /api/v1/auth/change-password
```

### Security Rules

- Never store plaintext passwords.
- Normalize email addresses.
- Use short-lived access tokens.
- Separate access and refresh tokens.
- Validate token type and expiry.
- Define revocation behaviour.
- Apply rate limiting.
- Never log credentials or tokens.

### Definition of Done

- Authentication flow works end to end.
- Invalid and expired tokens are rejected.
- Disabled users cannot authenticate.
- Authentication tests pass.

---

## 4.8 Module 2.8 — Authorization

### Roles

```text
platform_admin
organization_owner
organization_admin
engineer
viewer
```

### Authorization Requirements

- Check role.
- Check organization membership.
- Check resource ownership or organization scope.
- Prevent cross-organization access.
- Do not depend only on frontend restrictions.
- Return appropriate HTTP status codes.

### Definition of Done

- Authorization matrix is documented.
- Positive and negative permission tests pass.
- Cross-tenant access is blocked.

---

## 4.9 Module 2.9 — User and Organization Management

### User Features

- View profile.
- Update profile.
- Change password.
- View status and role.
- View recent activity.

### Organization Features

- Create default organization during registration.
- View current organization.
- List members.
- Add or invite members later.
- Update organization metadata.
- Validate membership.

### Admin Features

- List users.
- Search users.
- Filter by status and role.
- Change role.
- Disable account.
- Enable account.

### Definition of Done

- User profile works.
- Default organization workflow works.
- Organization isolation is tested.
- Admin user-management APIs work.

---

## 4.10 Module 2.10 — API Standards

### Base Path

```text
/api/v1
```

### Collection Format

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total_items": 0,
    "total_pages": 0
  }
}
```

### Error Format

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource could not be found.",
    "details": {},
    "request_id": "..."
  }
}
```

### Definition of Done

- All APIs use shared response patterns.
- Validation errors are standardized.
- Request IDs appear in errors.
- OpenAPI is complete.

---

## 4.11 Module 2.11 — Audit Foundation

### Initial Audit Events

- User registration
- Successful login
- Failed login
- Password change
- Role change
- User disabled
- User enabled
- Organization created
- Project created
- Incident created
- Analysis started
- Incident resolved

### Definition of Done

- Audit events are immutable through normal APIs.
- Sensitive data is excluded.
- Admin access is protected.
- Audit tests pass.

---

## 4.12 Phase 2 Quality Gate

- [ ] Migrations work on a clean database.
- [ ] Core models exist.
- [ ] Repository layer is tested.
- [ ] Service layer is tested.
- [ ] Authentication works.
- [ ] Authorization works.
- [ ] Organization isolation works.
- [ ] User management works.
- [ ] API responses are standardized.
- [ ] Audit events are recorded.
- [ ] Ruff passes.
- [ ] MyPy passes.
- [ ] Unit tests pass.
- [ ] Integration tests pass.
- [ ] Security tests pass.
- [ ] Documentation is updated.

---

# PHASE 3 — BUSINESS DOMAIN

## 5. Phase 3 Goal

Implement the primary DevGuard AI business workflow:

```text
Organization
    ↓
Project
    ↓
Pipeline Run
    ↓
Incident
    ↓
Uploaded Files
    ↓
Analysis Run
    ↓
Prediction, Evidence and Recommendations
    ↓
Resolution
    ↓
Incident Report
```

The Incident is the central business object.

---

## 5.1 Module 3.1 — Project Management

### Goal

Allow users to create and manage DevOps projects.

### Project Fields

```text
id
organization_id
name
slug
description
status
repository_url
default_branch
pipeline_provider
created_by
created_at
updated_at
```

### Features

- Create project
- List projects
- View project
- Update project
- Archive project
- Restore project
- Search projects
- Filter by status and provider
- View project statistics
- Validate organization scope

### Endpoints

```text
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
POST   /api/v1/projects/{project_id}/archive
POST   /api/v1/projects/{project_id}/restore
GET    /api/v1/projects/{project_id}/statistics
```

### Validation Rules

- Name is required.
- Slug is unique within the organization.
- Archived projects cannot receive new incidents unless restored.
- Repository URL must be valid when supplied.
- Users require project-management permission.

### Definition of Done

- Project CRUD works.
- Organization isolation is enforced.
- Archive and restore work.
- Project tests and documentation are complete.

---

## 5.2 Module 3.2 — Project Integrations

### Goal

Store project-level CI/CD and repository integration settings.

### Initial Providers

```text
GitHub Actions
Manual Upload
```

Later providers:

```text
GitLab CI
Jenkins
Azure DevOps
```

### Integration Fields

```text
id
project_id
provider
repository_identifier
configuration
status
last_verified_at
created_at
updated_at
```

### Security Rules

- Do not store plaintext access tokens.
- Encrypt credentials when persistent storage is required.
- Redact credentials from API responses.
- Provide connection-test behaviour.
- Store only required permissions.

### Definition of Done

- Manual-upload provider works.
- GitHub metadata can be stored.
- Secrets are protected.
- Integration configuration is tested.

---

## 5.3 Module 3.3 — Pipeline Run Management

### Goal

Represent CI/CD execution context associated with incidents.

### Pipeline Run Fields

```text
id
organization_id
project_id
provider
external_run_id
workflow_name
branch
commit_sha
commit_message
status
started_at
completed_at
duration_seconds
triggered_by
metadata
created_at
updated_at
```

### Features

- Create pipeline run manually.
- Import run metadata.
- List project runs.
- View run details.
- Filter by status, branch and date.
- Associate a run with an incident.
- Prevent duplicate external run IDs within a project.

### Endpoints

```text
POST /api/v1/projects/{project_id}/pipeline-runs
GET  /api/v1/projects/{project_id}/pipeline-runs
GET  /api/v1/pipeline-runs/{run_id}
```

### Definition of Done

- Pipeline runs persist correctly.
- Duplicate handling works.
- Filtering works.
- Runs can be linked to incidents.

---

## 5.4 Module 3.4 — Incident Management

### Goal

Implement the primary business object and lifecycle.

### Incident Fields

```text
id
organization_id
project_id
pipeline_run_id
incident_number
title
description
status
severity
priority
failure_stage
created_by
assigned_to
detected_at
resolved_at
created_at
updated_at
```

### Incident Statuses

```text
open
collecting_data
ready_for_analysis
analysis_queued
analysing
analysis_completed
needs_review
resolved
closed
failed
```

### Severity Levels

```text
critical
high
medium
low
informational
```

### Features

- Create incident
- List incidents
- View incident
- Update incident
- Assign incident
- Change severity
- Change priority
- Transition status
- Add tags
- Archive or close
- Search and filter
- View incident summary
- View incident AI status

### Endpoints

```text
POST   /api/v1/incidents
GET    /api/v1/incidents
GET    /api/v1/incidents/{incident_id}
PATCH  /api/v1/incidents/{incident_id}
POST   /api/v1/incidents/{incident_id}/assign
POST   /api/v1/incidents/{incident_id}/status
POST   /api/v1/incidents/{incident_id}/close
```

### State-Transition Rules

- Closed incidents cannot be edited without reopening.
- Analysis cannot start without valid input files.
- Resolved incidents require resolution data.
- Failed analysis does not automatically close an incident.
- Every status transition creates an incident event.

### Definition of Done

- Incident lifecycle works.
- Invalid transitions are rejected.
- Incident events are created.
- Filtering and pagination work.
- Authorization is enforced.
- Tests pass.

---

## 5.5 Module 3.5 — Incident Timeline

### Goal

Create a chronological record of incident activity.

### Event Types

```text
incident_created
status_changed
severity_changed
priority_changed
assigned
file_uploaded
file_validated
analysis_queued
analysis_started
analysis_completed
analysis_failed
note_added
recommendation_updated
resolution_added
report_generated
incident_closed
```

### Event Fields

```text
id
incident_id
event_type
actor_id
message
metadata
created_at
```

### Definition of Done

- Timeline events are generated automatically.
- Events are ordered correctly.
- Users can view the incident timeline.
- Events cannot be altered through ordinary APIs.

---

## 5.6 Module 3.6 — Incident Notes

### Goal

Allow engineers to add investigation notes.

### Features

- Add note
- Edit own note
- Delete own note according to policy
- List notes
- Mention analysis findings
- Distinguish human notes from AI-generated summaries

### Endpoints

```text
POST   /api/v1/incidents/{incident_id}/notes
GET    /api/v1/incidents/{incident_id}/notes
PATCH  /api/v1/incidents/{incident_id}/notes/{note_id}
DELETE /api/v1/incidents/{incident_id}/notes/{note_id}
```

### Definition of Done

- Notes are organization scoped.
- Permissions are enforced.
- Timeline events are created.
- Tests pass.

---

## 5.7 Module 3.7 — File Upload

### Goal

Allow users to upload CI/CD logs, workflow files and IaC files.

### Supported File Types

Initial scope:

```text
CI/CD log
GitHub Actions workflow YAML
Terraform file
Terraform plan output
Plain-text diagnostic file
JSON metadata file
```

### Features

- Multipart upload
- Multiple-file upload
- File metadata storage
- MIME validation
- Extension validation
- Size validation
- Hash generation
- Duplicate detection
- Safe filename generation
- Incident association
- Upload progress support
- File-status tracking

### Endpoints

```text
POST   /api/v1/incidents/{incident_id}/files
GET    /api/v1/incidents/{incident_id}/files
GET    /api/v1/files/{file_id}
DELETE /api/v1/files/{file_id}
```

### Security Requirements

- Reject executable files.
- Do not trust MIME type alone.
- Apply file-size limits.
- Prevent path traversal.
- Store generated filenames.
- Scan or safely isolate uploads.
- Redact secrets before AI processing.
- Prevent cross-organization file access.

### Definition of Done

- Valid files upload successfully.
- Invalid files are rejected safely.
- Duplicate handling works.
- File metadata is stored.
- Security tests pass.

---

## 5.8 Module 3.8 — File Validation and Preprocessing

### Goal

Validate and prepare uploaded files for later AI analysis.

### Validation Pipeline

```text
Upload
    ↓
Type Detection
    ↓
Size Validation
    ↓
Content Validation
    ↓
Encoding Detection
    ↓
Secret Redaction
    ↓
Normalization
    ↓
Metadata Extraction
    ↓
Ready for Analysis
```

### Processing Tasks

- Normalize line endings.
- Detect UTF-8 compatibility.
- Parse YAML syntax.
- Parse Terraform syntax where possible.
- Detect empty files.
- Detect truncated logs.
- Detect unsupported binary content.
- Extract line count.
- Extract workflow metadata.
- Extract Terraform resource metadata.
- Redact secrets.
- Store validation result.

### File Statuses

```text
uploaded
validating
valid
invalid
quarantined
processing_failed
```

### Definition of Done

- Every uploaded file has a validation result.
- Invalid files include safe reasons.
- Secrets are redacted before downstream processing.
- Preprocessing tests pass.

---

## 5.9 Module 3.9 — Analysis Run Orchestration

### Goal

Create a controlled record for each AI analysis execution.

### Analysis Run Fields

```text
id
organization_id
incident_id
status
analysis_version
requested_by
queued_at
started_at
completed_at
failure_reason
configuration
created_at
updated_at
```

### Statuses

```text
pending
queued
preprocessing
classifying
extracting_evidence
retrieving_context
reasoning
generating_recommendations
completed
failed
cancelled
```

### Features

- Create analysis run.
- Validate incident readiness.
- Prevent conflicting active runs.
- Track current stage.
- Track timestamps.
- Store safe failure details.
- Retry failed run.
- Cancel queued run.
- Associate outputs with the run.
- Preserve historical runs.

### Endpoints

```text
POST /api/v1/incidents/{incident_id}/analysis-runs
GET  /api/v1/incidents/{incident_id}/analysis-runs
GET  /api/v1/analysis-runs/{analysis_run_id}
POST /api/v1/analysis-runs/{analysis_run_id}/retry
POST /api/v1/analysis-runs/{analysis_run_id}/cancel
```

### Definition of Done

- Analysis runs can be created.
- Readiness validation works.
- Status progression works.
- Failed runs preserve error context.
- Historical runs remain accessible.
- Tests pass.

---

## 5.10 Module 3.10 — Incident Assignment

### Goal

Allow incidents to be assigned to engineers.

### Features

- Assign user
- Reassign user
- Unassign user
- List assignment history
- Validate organization membership
- Create timeline events
- Notify assigned user

### Definition of Done

- Only eligible organization members can be assigned.
- Assignment changes are audited.
- Notification records are created.
- Tests pass.

---

## 5.11 Module 3.11 — Resolution Management

### Goal

Record the final resolution of an incident.

### Resolution Fields

```text
id
incident_id
resolved_by
root_cause_summary
resolution_summary
actions_taken
prevention_actions
resolution_type
resolved_at
created_at
updated_at
```

### Features

- Add resolution
- Update resolution before closure
- Link accepted recommendation
- Add prevention action
- Resolve incident
- Reopen incident
- Preserve resolution history

### Rules

- Root cause summary is required.
- Resolution summary is required.
- Only authorized users can resolve.
- Resolution creates a timeline event.
- Resolution does not delete AI findings.
- Reopening preserves previous resolution details.

### Definition of Done

- Incidents can be resolved and reopened.
- Resolution data is validated.
- Audit and timeline events are created.
- Tests pass.

---

## 5.12 Module 3.12 — Incident Reports Foundation

### Goal

Prepare structured incident reports before PDF generation is implemented later.

### Report Sections

```text
Incident Overview
Project and Pipeline Context
Failure Classification
Evidence
Root Cause Analysis
Recommendations
Human Notes
Resolution
Timeline
Model and Analysis Metadata
```

### Features

- Build report data structure.
- Generate report preview JSON.
- Store report version.
- Link report to incident and analysis run.
- Track generated-by user.
- Preserve historical report versions.

### Endpoint

```text
POST /api/v1/incidents/{incident_id}/reports
GET  /api/v1/incidents/{incident_id}/reports
GET  /api/v1/reports/{report_id}
```

### Definition of Done

- Structured report data can be generated.
- Historical versions remain accessible.
- Report generation does not modify incident findings.

---

# 6. Phase 3 API Deliverables

At minimum:

```text
POST   /api/v1/projects
GET    /api/v1/projects
GET    /api/v1/projects/{project_id}
PATCH  /api/v1/projects/{project_id}
POST   /api/v1/projects/{project_id}/archive
POST   /api/v1/projects/{project_id}/restore

POST   /api/v1/projects/{project_id}/pipeline-runs
GET    /api/v1/projects/{project_id}/pipeline-runs
GET    /api/v1/pipeline-runs/{run_id}

POST   /api/v1/incidents
GET    /api/v1/incidents
GET    /api/v1/incidents/{incident_id}
PATCH  /api/v1/incidents/{incident_id}
POST   /api/v1/incidents/{incident_id}/assign
POST   /api/v1/incidents/{incident_id}/status
POST   /api/v1/incidents/{incident_id}/close

POST   /api/v1/incidents/{incident_id}/notes
GET    /api/v1/incidents/{incident_id}/notes

POST   /api/v1/incidents/{incident_id}/files
GET    /api/v1/incidents/{incident_id}/files
GET    /api/v1/files/{file_id}
DELETE /api/v1/files/{file_id}

POST /api/v1/incidents/{incident_id}/analysis-runs
GET  /api/v1/incidents/{incident_id}/analysis-runs
GET  /api/v1/analysis-runs/{analysis_run_id}
POST /api/v1/analysis-runs/{analysis_run_id}/retry
POST /api/v1/analysis-runs/{analysis_run_id}/cancel

POST /api/v1/incidents/{incident_id}/resolve
POST /api/v1/incidents/{incident_id}/reopen

POST /api/v1/incidents/{incident_id}/reports
GET  /api/v1/incidents/{incident_id}/reports
GET  /api/v1/reports/{report_id}
```

---

# 7. Testing Strategy for Part 2

## Unit Tests

- Models
- Enums
- Repositories
- Services
- Validation
- Authentication
- Authorization
- State transitions
- File validation
- Report builders

## Integration Tests

- Database migrations
- Registration and login
- Organization creation
- Project lifecycle
- Incident lifecycle
- File upload
- Analysis-run creation
- Resolution flow
- Report-data generation

## Security Tests

- Cross-organization access
- Invalid tokens
- Expired tokens
- Disabled accounts
- Unauthorized role actions
- Unsafe file uploads
- Path traversal
- Secret exposure
- Sensitive error responses

## Quality Commands

```bash
ruff check .
ruff format --check .
mypy app
pytest
alembic upgrade head
```

---

# 8. Documentation Required for Part 2

Create or update:

```text
README.md
PROJECT_CONSTITUTION.md
MASTER_ARCHITECTURE.md
DATABASE_ARCHITECTURE.md
API_SPECIFICATION.md
AUTHENTICATION_GUIDE.md
AUTHORIZATION_MATRIX.md
PROJECT_MANAGEMENT_GUIDE.md
INCIDENT_LIFECYCLE.md
FILE_UPLOAD_GUIDE.md
ANALYSIS_RUN_GUIDE.md
TESTING_GUIDE.md
DEVELOPMENT_SETUP.md
```

---

# 9. Part 2 Progress Tracker

| Module | Status | Progress |
|---|---|---:|
| 1.1 Repository and Governance | ⬜ Not Started | 0% |
| 1.2 Project Structure | ⬜ Not Started | 0% |
| 1.3 Backend Skeleton | ⬜ Not Started | 0% |
| 1.4 Frontend Skeleton | ⬜ Not Started | 0% |
| 1.5 Docker Environment | ⬜ Not Started | 0% |
| 1.6 Configuration and Secrets | ⬜ Not Started | 0% |
| 1.7 Logging and Observability | ⬜ Not Started | 0% |
| 2.1 Database Foundation | ⬜ Not Started | 0% |
| 2.2 Core Enums | ⬜ Not Started | 0% |
| 2.3 Core Models | ⬜ Not Started | 0% |
| 2.4 Migrations | ⬜ Not Started | 0% |
| 2.5 Repository Layer | ⬜ Not Started | 0% |
| 2.6 Service Layer | ⬜ Not Started | 0% |
| 2.7 Authentication | ⬜ Not Started | 0% |
| 2.8 Authorization | ⬜ Not Started | 0% |
| 2.9 User and Organization Management | ⬜ Not Started | 0% |
| 2.10 API Standards | ⬜ Not Started | 0% |
| 2.11 Audit Foundation | ⬜ Not Started | 0% |
| 3.1 Project Management | ⬜ Not Started | 0% |
| 3.2 Project Integrations | ⬜ Not Started | 0% |
| 3.3 Pipeline Runs | ⬜ Not Started | 0% |
| 3.4 Incident Management | ⬜ Not Started | 0% |
| 3.5 Incident Timeline | ⬜ Not Started | 0% |
| 3.6 Incident Notes | ⬜ Not Started | 0% |
| 3.7 File Upload | ⬜ Not Started | 0% |
| 3.8 File Validation | ⬜ Not Started | 0% |
| 3.9 Analysis Run Orchestration | ⬜ Not Started | 0% |
| 3.10 Incident Assignment | ⬜ Not Started | 0% |
| 3.11 Resolution Management | ⬜ Not Started | 0% |
| 3.12 Incident Reports Foundation | ⬜ Not Started | 0% |

---

# 10. Part 2 Completion Criteria

Part 2 is complete only when:

- The development environment is reproducible.
- Backend and frontend foundations are stable.
- Database migrations work from a clean database.
- Users can register and authenticate.
- Roles and organization isolation are enforced.
- Projects can be created and managed.
- Pipeline runs can be recorded.
- Incidents can move through a validated lifecycle.
- Users can upload and validate supported files.
- Analysis runs can be created and tracked.
- Notes, assignments and timeline events work.
- Incidents can be resolved and reopened.
- Structured incident-report data can be generated.
- Unit, integration and security tests pass.
- Swagger is complete.
- Required documentation is updated.
- No critical TODOs or warnings remain.

---

# 11. Output of Part 2

The completed workflow should be:

```text
User Registration
        ↓
Organization Creation
        ↓
Project Creation
        ↓
Pipeline Run Registration
        ↓
Incident Creation
        ↓
File Upload and Validation
        ↓
Analysis Run Creation
        ↓
AI Modules Executed in Later Phases
        ↓
Incident Review
        ↓
Resolution
        ↓
Report
```

---

# Part 3 — Dataset, Machine Learning and AI Intelligence

## 1. Purpose

Part 3 defines the complete AI implementation roadmap for DevGuard AI.

It transforms uploaded CI/CD artifacts into explainable AI insights through a structured pipeline.

Implementation sequence:

```text
Uploaded Files
        ↓
Dataset Collection
        ↓
Dataset Validation
        ↓
Dataset Annotation
        ↓
Feature Engineering
        ↓
Machine Learning Classification
        ↓
Evidence Extraction
        ↓
Knowledge Base (RAG)
        ↓
LLM Root Cause Analysis
        ↓
Recommendation Generation
        ↓
Confidence Scoring
        ↓
Evaluation
```

---

# PHASE 4 — DATASET PIPELINE

## Goal

Build a high-quality, reproducible dataset for training and evaluating DevGuard AI.

## Module 4.1 — Dataset Schema

Tasks:

- Design dataset schema
- Define labels
- Create metadata format
- Version dataset
- Define train/validation/test split
- Document schema

Deliverables:

```text
train.jsonl
validation.jsonl
test.jsonl
dataset_schema.json
label_dictionary.json
```

Definition of Done:

- Schema approved
- Dataset versioned
- Validation passes

---

## Module 4.2 — Data Collection

Sources:

- GitHub Actions logs
- GitHub workflow YAML
- Terraform
- Terraform plan
- Open-source CI/CD failures
- Synthetic failures for missing classes

Tasks:

- Collect logs
- Remove duplicates
- Store metadata
- Organize by category
- Track provenance

Definition of Done:

- Required categories collected
- Provenance recorded
- No duplicate samples

---

## Module 4.3 — Dataset Annotation

Tasks:

- Assign failure category
- Assign severity
- Assign failure stage
- Identify evidence
- Create gold-standard root cause
- Create gold-standard recommendation

Annotation fields:

```text
failure_category
severity
pipeline_stage
evidence
root_cause
recommendation
confidence
```

Definition of Done:

- Labels reviewed
- Annotation guide documented
- Dataset consistency verified

---

## Module 4.4 — Dataset Validation

Validation checks:

- Missing labels
- Duplicate records
- Invalid JSON
- Unsupported files
- Broken references
- Label imbalance
- Encoding validation

Definition of Done:

- Dataset passes validation
- Validation report generated

---

# PHASE 5 — MACHINE LEARNING

## Goal

Train the initial failure-classification model.

## Module 5.1 — Preprocessing

Tasks:

- Text normalization
- Secret redaction
- Tokenization
- Stop-word handling
- Feature extraction
- Train/test preparation

Definition of Done:

- Reproducible preprocessing pipeline

---

## Module 5.2 — Model Training

Initial models:

- Logistic Regression
- Random Forest

Future:

- XGBoost
- LightGBM
- Transformer encoder

Metrics:

- Accuracy
- Precision
- Recall
- F1
- Top-K Accuracy

Definition of Done:

- Best model selected
- Serialized model stored
- Version registered

---

## Module 5.3 — Prediction Service

Responsibilities:

- Load model
- Predict failure category
- Return probability scores
- Return top-K predictions
- Log inference metadata

Definition of Done:

- Prediction API available
- Response latency measured

---

# PHASE 6 — AI INTELLIGENCE ENGINE

## Goal

Transform ML predictions into explainable AI investigations.

---

## Module 6.1 — Evidence Extraction

Tasks:

- Extract failed steps
- Extract error messages
- Extract stack traces
- Extract workflow metadata
- Extract Terraform resources
- Rank evidence relevance

Outputs:

```text
Evidence Items
Evidence Confidence
Evidence Summary
```

Definition of Done:

- Evidence linked to incident
- Confidence calculated

---

## Module 6.2 — Knowledge Base (RAG)

Tasks:

- Build document corpus
- Chunk documentation
- Generate embeddings
- Store vectors
- Retrieve relevant context
- Rank retrieved documents

Knowledge Sources:

- GitHub documentation
- Terraform documentation
- Internal guidance
- Best practices

Definition of Done:

- Relevant context retrieved
- Retrieval latency acceptable

---

## Module 6.3 — LLM Reasoning

Responsibilities:

- Combine prediction
- Combine evidence
- Combine retrieved documentation
- Generate root cause
- Explain reasoning
- Identify uncertainty

Outputs:

```text
Root Cause
Reasoning
Supporting Evidence
Limitations
```

Definition of Done:

- Explainable reasoning generated
- Hallucination guardrails applied

---

## Module 6.4 — Recommendation Engine

Generate:

- Immediate fix
- Long-term prevention
- Best practices
- Security improvements
- Reliability improvements

Each recommendation should include:

```text
Priority
Impact
Risk
Estimated Effort
Confidence
```

Definition of Done:

- Recommendations generated
- Ranked by priority
- Linked to evidence

---

## Module 6.5 — Confidence Scoring

Confidence should combine:

- ML probability
- Evidence quality
- RAG relevance
- LLM consistency

Levels:

```text
High
Medium
Low
```

Definition of Done:

- Confidence visible in analysis output
- Confidence formula documented

---

# AI PIPELINE

```text
Incident
        ↓
Uploaded Files
        ↓
Validation
        ↓
Preprocessing
        ↓
Machine Learning
        ↓
Evidence Extraction
        ↓
RAG Retrieval
        ↓
LLM Reasoning
        ↓
Recommendations
        ↓
Confidence
        ↓
Database
```

---

# Testing Strategy

Unit Tests

- Dataset validators
- Feature extraction
- ML inference
- Evidence extraction
- RAG retrieval
- Prompt builders

Integration Tests

- End-to-end AI pipeline
- Prediction service
- Retrieval service
- Recommendation generation

Evaluation

- Accuracy
- Precision
- Recall
- F1 Score
- Top-K Accuracy
- Response Time
- User usefulness ratings

---

# Deliverables

- Versioned dataset
- Trained ML model
- Prediction API
- Evidence extraction engine
- Vector database
- RAG service
- Prompt templates
- LLM integration
- Recommendation engine
- Confidence scoring
- Evaluation report

---

# Progress Tracker

| Module | Status |
|---|---|
| Dataset Schema | ⬜ |
| Data Collection | ⬜ |
| Dataset Annotation | ⬜ |
| Dataset Validation | ⬜ |
| Preprocessing | ⬜ |
| Model Training | ⬜ |
| Prediction Service | ⬜ |
| Evidence Extraction | ⬜ |
| Knowledge Base | ⬜ |
| LLM Reasoning | ⬜ |
| Recommendation Engine | ⬜ |
| Confidence Scoring | ⬜ |

---

# Completion Criteria

Part 3 is complete when:

- Dataset is versioned and validated.
- ML model is trained and evaluated.
- Prediction API works.
- Evidence extraction is operational.
- RAG retrieves relevant documentation.
- LLM generates explainable root causes.
- Recommendations are ranked.
- Confidence scores are calculated.
- AI pipeline works end-to-end.
- Evaluation metrics are produced.

---

# Part 4 — Enterprise Frontend and Integration

## 1. Purpose

Part 4 defines the implementation roadmap for the complete DevGuard AI frontend application.

It converts the approved UI/UX specification into a production-quality React application connected to the backend and AI services.

This part covers:

- Frontend architecture
- Design system
- Authentication experience
- Dashboard
- Projects
- Pipeline runs
- Incidents
- File upload
- AI analysis
- Evidence viewer
- Recommendations
- Reports
- Analytics
- Settings
- Administration
- Error handling
- Accessibility
- Responsive behaviour
- API integration
- End-to-end frontend testing

---

# PHASE 7 — ENTERPRISE FRONTEND

## 2. Phase Goal

Build a secure, consistent and responsive enterprise SaaS interface that allows users to manage DevOps incidents and understand AI-generated investigations.

The frontend must:

- Follow the approved dark enterprise design system.
- Use reusable components.
- Support role-based access.
- Display loading, empty, success and error states.
- Avoid exposing sensitive information.
- Integrate cleanly with all backend APIs.
- Remain usable on desktop, tablet and mobile.
- Support accessibility requirements.

---

# 3. Frontend Technology Stack

Recommended stack:

```text
React
TypeScript
Vite
React Router
TanStack Query
Zustand or Redux Toolkit
React Hook Form
Zod
Axios or Fetch wrapper
Recharts
Lucide Icons
CSS Modules, Tailwind CSS or styled component system
Vitest
React Testing Library
Playwright
```

Selection should remain consistent throughout the application.

---

# 4. Frontend Architecture

## 4.1 Recommended Folder Structure

```text
frontend/
├── public/
├── src/
│   ├── app/
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   ├── providers.tsx
│   │   └── queryClient.ts
│   ├── assets/
│   ├── components/
│   │   ├── common/
│   │   ├── data-display/
│   │   ├── feedback/
│   │   ├── forms/
│   │   ├── layout/
│   │   ├── navigation/
│   │   └── overlays/
│   ├── features/
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── projects/
│   │   ├── pipeline-runs/
│   │   ├── incidents/
│   │   ├── files/
│   │   ├── analysis/
│   │   ├── evidence/
│   │   ├── recommendations/
│   │   ├── reports/
│   │   ├── analytics/
│   │   ├── settings/
│   │   └── admin/
│   ├── hooks/
│   ├── layouts/
│   ├── pages/
│   ├── services/
│   │   ├── apiClient.ts
│   │   ├── authApi.ts
│   │   ├── projectApi.ts
│   │   ├── incidentApi.ts
│   │   ├── analysisApi.ts
│   │   └── reportApi.ts
│   ├── stores/
│   ├── styles/
│   ├── types/
│   ├── utils/
│   └── main.tsx
├── tests/
├── package.json
└── vite.config.ts
```

## 4.2 Architecture Rules

- Pages should compose feature components.
- API calls should be isolated inside service modules.
- Server state should be handled by TanStack Query.
- Global client state should be limited.
- Forms should use shared validation schemas.
- Role checks should use reusable permission helpers.
- Route-level code splitting should be enabled.
- Reusable components must not contain page-specific assumptions.

---

# MODULE 7.1 — DESIGN SYSTEM FOUNDATION

## Goal

Create the reusable visual language for the entire application.

## Theme

```text
Background:       #0B1220
Surface:          #111827
Elevated Surface: #1A2333
Primary:          #2563EB
Secondary:        #7C3AED
Success:          #10B981
Warning:          #F59E0B
Danger:           #EF4444
Information:      #06B6D4
Border:           rgba(255,255,255,0.06)
```

Typography:

```text
Font: Inter
Page Title: 32px Bold
Section Title: 22px Semibold
Card Title: 18px Semibold
Body: 15px Regular
Caption: 13px Regular
```

Spacing:

```text
8px spacing system
```

Radius:

```text
Cards: 14px
Buttons: 12px
Inputs: 12px
```

Button height:

```text
44px
```

## Components

Create:

- Button
- IconButton
- Input
- Textarea
- Select
- Checkbox
- Radio
- Toggle
- Badge
- StatusBadge
- SeverityBadge
- Card
- MetricCard
- EmptyState
- Skeleton
- Spinner
- Toast
- Alert
- Modal
- Drawer
- Dropdown
- Tooltip
- Tabs
- Breadcrumb
- Pagination
- DataTable
- CodeViewer
- Timeline
- Stepper
- ProgressBar
- ConfidenceIndicator
- Avatar
- UserMenu

## Component States

Every interactive component must support:

- Default
- Hover
- Focus
- Active
- Disabled
- Loading
- Error where relevant

## Definition of Done

- Component documentation exists.
- Design tokens are centralized.
- Components pass visual review.
- Keyboard navigation works.
- Contrast is acceptable.
- Reuse is demonstrated across multiple pages.

---

# MODULE 7.2 — APPLICATION SHELL

## Goal

Implement the global application layout.

## Layout

```text
Sidebar: 240px
Top Bar: 72px
Content Area: responsive
```

## Sidebar Navigation

Recommended items:

```text
Dashboard
Projects
Incidents
Analytics
Reports
Knowledge Base
Model Evaluation
Settings
Admin
```

Visibility depends on role.

## Top Bar

Include:

- Workspace or organization selector
- Global search
- Notifications
- Help
- User profile menu

## Features

- Collapsible sidebar
- Active route state
- Breadcrumbs
- Responsive drawer on smaller screens
- Route-level loading state
- Global error boundary
- Session-expiry handling

## Definition of Done

- Shell is consistent across protected routes.
- Navigation is role-aware.
- Responsive behaviour works.
- Session expiry redirects safely.
- Keyboard navigation works.

---

# MODULE 7.3 — ROUTING AND ROUTE PROTECTION

## Goal

Implement secure application routing.

## Public Routes

```text
/login
/register
/forgot-password
/reset-password
```

## Protected Routes

```text
/dashboard
/projects
/projects/:projectId
/projects/:projectId/pipeline-runs
/incidents
/incidents/:incidentId
/incidents/:incidentId/analysis
/incidents/:incidentId/evidence
/incidents/:incidentId/recommendations
/incidents/:incidentId/timeline
/reports
/reports/:reportId
/analytics
/settings/profile
/settings/security
/settings/organization
/admin/users
/admin/models
/admin/evaluations
/admin/audit
```

## Requirements

- Authentication guard
- Permission guard
- Organization-context guard
- Not-found route
- Forbidden route
- Session-expired route
- Lazy-loaded pages

## Definition of Done

- Unauthorized users cannot access protected pages.
- Forbidden pages show a safe 403 state.
- Unknown routes show 404.
- Route-level loading works.
- Direct URL navigation works.

---

# MODULE 7.4 — AUTHENTICATION EXPERIENCE

## Goal

Build the complete sign-in and account-access flow.

## Screens

- Login
- Register
- Forgot password
- Reset password
- Session expired
- Account disabled

## Login Features

- Email field
- Password field
- Show/hide password
- Remember-me option if supported
- Loading state
- Validation messages
- Safe authentication error
- Redirect to intended route after login

## Registration Features

- Full name
- Email
- Password
- Confirm password
- Terms acknowledgement
- Password-strength guidance
- Automatic default organization creation

## Security Requirements

- Never persist raw passwords.
- Do not expose token values in the UI.
- Clear authentication state on logout.
- Handle refresh failure safely.
- Avoid revealing account existence.

## Definition of Done

- Login and registration work end to end.
- Errors are understandable.
- Form validation matches backend rules.
- Token refresh is transparent.
- Logout clears session data.

---

# MODULE 7.5 — DASHBOARD

## Goal

Provide an operational overview of projects, incidents and AI activity.

## Dashboard Sections

### Header

- Page title
- Date range selector
- Refresh action
- Create incident button

### Key Metrics

- Open incidents
- Critical incidents
- Mean time to resolution
- Analyses completed
- AI confidence average
- Resolution rate

### Charts

- Incidents over time
- Incidents by severity
- Failures by category
- Analysis outcomes
- Resolution trend

### Tables and Lists

- Recent incidents
- Active analyses
- High-risk recommendations
- Recently updated projects
- Latest reports

## States

- Loading skeleton
- No data
- Partial data
- API error
- Permission-restricted data

## Definition of Done

- Metrics are sourced from APIs.
- Charts respond to date filters.
- Recent records link to detail pages.
- Empty state guides the user.
- Dashboard loads within acceptable time.

---

# MODULE 7.6 — PROJECT LIST

## Goal

Allow users to view and manage projects.

## Features

- Search
- Status filter
- Pipeline provider filter
- Sort
- Pagination
- Grid and table view where useful
- Create project
- Archive project
- Restore project

## Project Card or Row

Display:

```text
Project name
Description
Status
Repository
Pipeline provider
Open incidents
Last activity
```

## Definition of Done

- Project list is organization scoped.
- Filters update results.
- Pagination works.
- Create and archive actions enforce permissions.
- Empty and error states are implemented.

---

# MODULE 7.7 — CREATE AND EDIT PROJECT

## Goal

Provide project configuration forms.

## Fields

- Name
- Slug
- Description
- Repository URL
- Default branch
- Pipeline provider
- Status

## Requirements

- Client-side validation
- Backend validation mapping
- Duplicate slug handling
- Unsaved-change warning
- Success feedback
- Cancel behaviour

## Definition of Done

- Projects can be created and edited.
- Validation messages are precise.
- Unsaved changes are protected.
- Success redirects correctly.

---

# MODULE 7.8 — PROJECT DETAIL

## Goal

Provide a complete operational view of one project.

## Tabs

```text
Overview
Pipeline Runs
Incidents
Integrations
Team
Settings
```

## Overview

Display:

- Project metadata
- Open-incident summary
- Failure-category breakdown
- Recent pipeline runs
- Recent incidents
- Analysis activity
- Integration status

## Definition of Done

- Project information loads from API.
- Tabs preserve route state.
- Restricted tabs are hidden or disabled appropriately.
- Linked entities open correct detail pages.

---

# MODULE 7.9 — PIPELINE RUNS

## Goal

Display CI/CD execution context.

## List Features

- Search
- Status filter
- Branch filter
- Date filter
- Duration
- Commit information
- Associated incident

## Detail View

Display:

```text
Provider
Workflow
Run ID
Status
Branch
Commit
Started time
Completed time
Duration
Triggering user
Metadata
Linked incident
```

## Definition of Done

- Runs load by project.
- Duplicate or incomplete metadata is handled gracefully.
- Linked incidents are accessible.
- Empty and error states are present.

---

# MODULE 7.10 — INCIDENT LIST

## Goal

Provide the primary operational work queue.

## Filters

- Search
- Project
- Status
- Severity
- Priority
- Assignee
- Failure category
- Date range

## Columns

```text
Incident number
Title
Project
Status
Severity
Priority
Assignee
AI analysis status
Created time
Updated time
```

## Features

- Saved filter state
- Pagination
- Sorting
- Bulk selection foundation
- Create incident
- Quick assignment where permitted
- Export foundation

## Definition of Done

- Filters map correctly to backend queries.
- Status and severity are visually clear.
- Large datasets remain usable.
- Permission checks apply to actions.

---

# MODULE 7.11 — CREATE INCIDENT

## Goal

Allow users to open a new incident.

## Fields

- Project
- Pipeline run
- Title
- Description
- Severity
- Priority
- Failure stage
- Assignee

## Workflow

```text
Create Incident
        ↓
Upload Files
        ↓
Validate Files
        ↓
Start Analysis
```

## Definition of Done

- Incident creation works.
- Project and pipeline-run selections are validated.
- User can continue directly to file upload.
- Errors preserve form data.

---

# MODULE 7.12 — INCIDENT DETAIL

## Goal

Create the central investigation workspace.

## Header

Display:

- Incident number
- Title
- Status
- Severity
- Priority
- Project
- Assignee
- Created time
- Primary actions

## Tabs

```text
Overview
AI Analysis
Evidence
Recommendations
Files
Timeline
Notes
Resolution
Reports
```

## Overview Sections

- Incident summary
- Pipeline context
- Current analysis status
- Top prediction
- Key evidence
- Highest-priority recommendations
- Activity summary

## Definition of Done

- All tabs use a shared incident context.
- Status transitions are reflected immediately.
- Actions enforce permissions.
- Loading and partial-data states are handled.

---

# MODULE 7.13 — FILE UPLOAD INTERFACE

## Goal

Provide a safe and understandable file-upload experience.

## Features

- Drag and drop
- File picker
- Multiple files
- Upload progress
- File type indicator
- Size display
- Validation status
- Duplicate warning
- Remove before upload
- Retry failed upload

## Supported Visual States

```text
Queued
Uploading
Validating
Valid
Invalid
Quarantined
Failed
```

## Requirements

- Clearly show supported formats.
- Clearly show maximum size.
- Display safe validation errors.
- Do not expose internal storage paths.
- Warn before deleting uploaded files.

## Definition of Done

- Upload progress works.
- Validation status updates.
- Invalid files are clearly explained.
- Retry and deletion work.
- Accessibility requirements are met.

---

# MODULE 7.14 — ANALYSIS RUN WORKSPACE

## Goal

Display the progress and result of AI analysis.

## Analysis Stages

```text
Preprocessing
Classification
Evidence Extraction
Context Retrieval
Root Cause Reasoning
Recommendation Generation
Completed
```

## Features

- Start analysis
- Confirm prerequisites
- Display queued state
- Live or polled progress
- Stage stepper
- Retry failed analysis
- Cancel queued analysis
- View previous runs
- Compare analysis versions foundation

## Failure State

Display:

- Safe error summary
- Failed stage
- Retry action
- Link to logs only for authorized roles
- Request ID

## Definition of Done

- Analysis state updates without full page refresh.
- Historical runs are accessible.
- Retry and cancel actions work.
- Failure state is understandable.

---

# MODULE 7.15 — AI ANALYSIS RESULT

## Goal

Present the AI investigation in an explainable format.

## Sections

### Executive Summary

- Root cause summary
- Overall confidence
- Severity
- Analysis completion time

### Classification

- Primary failure category
- Top-K alternatives
- Probability scores
- Model version

### Root Cause Reasoning

- Explanation
- Contributing factors
- Uncertainty
- Limitations

### Supporting Context

- Evidence references
- Retrieved documents
- Pipeline metadata

## Requirements

- Clearly separate AI conclusions from raw evidence.
- Clearly label low-confidence output.
- Never present uncertain output as proven fact.
- Allow user feedback.
- Show model and analysis version.

## Definition of Done

- Analysis is understandable without reading raw logs.
- Supporting evidence is directly accessible.
- Confidence is visible.
- Feedback can be submitted.

---

# MODULE 7.16 — EVIDENCE VIEWER

## Goal

Allow users to verify AI conclusions against source artifacts.

## Features

- Evidence list
- Evidence type filter
- Relevance score
- Source filename
- Line range
- Highlighted text
- Expand surrounding context
- Jump between evidence items
- Copy safe text
- Secret-redaction indicator

## Layout

Recommended two-panel layout:

```text
Left: Evidence list
Right: Source and highlighted context
```

## Definition of Done

- Evidence links to correct source lines.
- Long files remain performant.
- Redacted content is clearly marked.
- Evidence relevance is visible.
- Keyboard navigation works.

---

# MODULE 7.17 — RAG CONTEXT VIEWER

## Goal

Show the technical sources used by the AI.

## Display

- Document title
- Source type
- Relevance score
- Retrieved excerpt
- Document version or date where available
- Relationship to the analysis

## Requirements

- Distinguish uploaded evidence from retrieved documentation.
- Do not imply that retrieval proves the conclusion.
- Preserve source metadata.
- Allow context expansion where permitted.

## Definition of Done

- Retrieved documents are visible.
- Relevance scores are shown.
- Users can understand why each source was retrieved.

---

# MODULE 7.18 — RECOMMENDATIONS

## Goal

Present ranked remediation actions.

## Recommendation Card

Display:

```text
Title
Priority
Type
Impact
Risk
Estimated effort
Confidence
Evidence links
Suggested steps
```

## Categories

- Immediate fix
- Long-term prevention
- Security
- Reliability
- Cost optimization
- Process improvement

## User Actions

- Mark accepted
- Mark rejected
- Mark completed
- Add comment
- Link to resolution
- Submit usefulness feedback

## Definition of Done

- Recommendations are sorted by priority.
- Status changes persist.
- Evidence links work.
- Accepted recommendations can be linked to resolution.

---

# MODULE 7.19 — INCIDENT TIMELINE

## Goal

Display the chronological incident lifecycle.

## Timeline Events

- Incident created
- Assignment changed
- Severity changed
- File uploaded
- Analysis started
- Analysis completed
- Note added
- Recommendation updated
- Resolution added
- Report generated
- Incident closed

## Features

- Event-type filter
- Actor display
- Relative and exact time
- Expand metadata
- Group by date

## Definition of Done

- Events are chronologically correct.
- System, AI and human events are visually distinguishable.
- Event metadata is safe to display.

---

# MODULE 7.20 — NOTES AND COLLABORATION

## Goal

Allow engineers to document investigation work.

## Features

- Add note
- Edit own note
- Delete according to policy
- Markdown support where approved
- Mention users foundation
- Link evidence and recommendations
- Distinguish human notes from AI output

## Definition of Done

- Note permissions are enforced.
- Notes appear in the timeline.
- Input is sanitized.
- Error and empty states are implemented.

---

# MODULE 7.21 — RESOLUTION WORKFLOW

## Goal

Guide users through resolving and closing incidents.

## Form Sections

- Root cause summary
- Resolution summary
- Actions taken
- Prevention actions
- Accepted recommendations
- Resolution type
- Confirmation

## Actions

- Resolve
- Reopen
- Close
- Generate report

## Requirements

- Required fields must be validated.
- AI output may prefill suggestions but must remain editable.
- Human confirmation is required.
- Previous resolution history is preserved.

## Definition of Done

- Incident can be resolved and reopened.
- Resolution is linked to timeline and report.
- Human ownership of the final resolution is clear.

---

# MODULE 7.22 — REPORTS

## Goal

Allow users to preview and manage incident reports.

## Report List

Display:

- Report title
- Incident
- Project
- Generated time
- Generated by
- Version
- Status

## Report Detail

Sections:

```text
Incident Overview
Pipeline Context
Classification
Evidence
Root Cause
Recommendations
Timeline
Resolution
Model Metadata
```

## Features

- Generate report
- Preview report
- Download PDF in later integration
- Preserve versions
- Regenerate after resolution
- Permission control

## Definition of Done

- Structured report renders correctly.
- Versions are preserved.
- Report links to incident and analysis run.
- Missing sections are handled gracefully.

---

# MODULE 7.23 — ANALYTICS

## Goal

Provide operational and research insights.

## Metrics

- Incident count
- Severity distribution
- Failure-category distribution
- Mean time to resolution
- Analysis success rate
- Average confidence
- Recommendation acceptance rate
- Model accuracy
- Evidence precision
- Usefulness rating

## Filters

- Date range
- Project
- Severity
- Failure category
- Model version

## Charts

- Incident trend
- Failure-category bar chart
- Severity distribution
- Resolution-time trend
- Confidence distribution
- Model performance trend

## Definition of Done

- Filters update all widgets consistently.
- Research metrics are clearly labelled.
- Empty datasets are handled.
- Charts are accessible and responsive.

---

# MODULE 7.24 — NOTIFICATIONS

## Goal

Provide users with relevant operational updates.

## Notification Types

- Incident assigned
- Analysis completed
- Analysis failed
- Critical incident created
- Recommendation updated
- Incident resolved
- Report generated

## Features

- Notification menu
- Unread count
- Mark as read
- Mark all as read
- Navigate to related resource
- Notification preferences foundation

## Definition of Done

- Notifications link to valid resources.
- Read state persists.
- Unauthorized resource links are blocked.

---

# MODULE 7.25 — PROFILE AND SECURITY SETTINGS

## Goal

Allow users to manage personal account settings.

## Profile Settings

- Full name
- Avatar metadata
- Email display
- Role display
- Organization display

## Security Settings

- Change password
- View session information
- Logout all sessions where supported
- Security activity
- Multi-factor authentication placeholder for future release

## Definition of Done

- Profile updates persist.
- Security actions require confirmation.
- Sensitive actions are audited.

---

# MODULE 7.26 — ORGANIZATION SETTINGS

## Goal

Allow authorized users to manage organization configuration.

## Sections

- General information
- Members
- Roles
- Project defaults
- Data-retention foundation
- Notification settings
- Billing placeholder for commercial SaaS

## Definition of Done

- Settings are role protected.
- Member list is accurate.
- Changes are audited.
- Commercial placeholders do not block the MSc MVP.

---

# MODULE 7.27 — ADMIN USER MANAGEMENT

## Goal

Provide platform and organization administrators with user controls.

## Features

- User table
- Search
- Role filter
- Status filter
- View details
- Change role
- Disable
- Enable
- View activity
- View organization membership

## Definition of Done

- Admin actions require confirmation.
- Dangerous actions are clearly labelled.
- Last-admin protections are respected.
- Actions create audit records.

---

# MODULE 7.28 — ADMIN MODEL MANAGEMENT

## Goal

Allow administrators to inspect AI model versions.

## Display

```text
Model name
Model type
Version
Status
Training date
Dataset version
Metrics
Deployment status
```

## Features

- View model details
- Compare versions
- Activate or deactivate version foundation
- View evaluation results
- View known limitations

## Definition of Done

- Model metadata is visible.
- Activation actions are permission protected.
- Current production model is clear.

---

# MODULE 7.29 — ADMIN EVALUATION

## Goal

Display model and system evaluation results.

## Metrics

- Accuracy
- Precision
- Recall
- F1 score
- Top-K accuracy
- Evidence precision
- Retrieval relevance
- Recommendation usefulness
- Analysis latency
- Failure rate

## Definition of Done

- Metrics are associated with model and dataset versions.
- Charts and tables can be filtered.
- Evaluation limitations are shown.

---

# MODULE 7.30 — AUDIT LOG VIEWER

## Goal

Allow administrators to inspect protected audit events.

## Filters

- User
- Organization
- Action
- Resource type
- Date range
- Result

## Display

- Timestamp
- Actor
- Action
- Resource
- Request ID
- Safe metadata

## Definition of Done

- Audit data is read-only.
- Sensitive data is excluded.
- Access is strictly restricted.
- Pagination and filtering work.

---

# MODULE 7.31 — GLOBAL SEARCH

## Goal

Allow users to locate operational records quickly.

## Searchable Entities

- Projects
- Pipeline runs
- Incidents
- Reports
- Users where permitted

## Features

- Search modal
- Keyboard shortcut
- Grouped results
- Recent searches
- Direct navigation
- Permission filtering

## Definition of Done

- Results respect organization and role boundaries.
- Search remains responsive.
- Empty and error states are clear.

---

# MODULE 7.32 — ERROR, EMPTY AND LOADING STATES

## Goal

Ensure every page behaves professionally in non-ideal conditions.

## Required Shared States

- Page loading
- Table loading
- Card loading
- Empty data
- Search with no results
- Permission denied
- Not found
- Network error
- API validation error
- Server error
- Analysis failure
- Partial-data warning

## Definition of Done

- No screen shows raw exceptions.
- Retry actions exist where appropriate.
- Empty states guide the next action.
- Skeletons reduce layout shift.

---

# MODULE 7.33 — ACCESSIBILITY

## Goal

Ensure the application is usable by a wider range of users.

## Requirements

- Semantic HTML
- Keyboard navigation
- Visible focus states
- Accessible labels
- Proper heading hierarchy
- Sufficient contrast
- Form-error association
- Screen-reader friendly status updates
- Reduced-motion support
- Accessible chart summaries
- No information communicated only by colour

## Definition of Done

- Core flows work without a mouse.
- Automated accessibility checks pass.
- Manual keyboard review is complete.

---

# MODULE 7.34 — RESPONSIVE DESIGN

## Goal

Support desktop, tablet and mobile usage.

## Breakpoints

Use project-approved breakpoints, for example:

```text
Mobile:  < 768px
Tablet:  768px–1199px
Desktop: ≥ 1200px
```

## Behaviour

- Sidebar becomes drawer.
- Tables support horizontal scrolling or responsive cards.
- Multi-column panels collapse.
- Modals fit smaller screens.
- Touch targets remain usable.
- Charts remain readable.

## Definition of Done

- Major workflows work at all target sizes.
- No critical content is hidden.
- No horizontal overflow exists outside intended containers.

---

# PHASE 8 — FRONTEND AND BACKEND INTEGRATION

## 5. Phase Goal

Connect the enterprise frontend to all backend and AI services reliably.

---

# MODULE 8.1 — API CLIENT

## Goal

Create one secure API communication layer.

## Responsibilities

- Base URL
- Request headers
- Access token attachment
- Token refresh
- Request ID handling
- Standard error mapping
- Timeout handling
- Cancellation
- File upload support

## Rules

- Components must not call raw endpoints directly.
- Authentication refresh must avoid retry loops.
- API errors should map to typed frontend errors.
- Tokens must not be written to logs.

## Definition of Done

- All API calls use the shared client.
- Refresh behaviour is tested.
- Network errors produce safe UI states.

---

# MODULE 8.2 — SERVER-STATE MANAGEMENT

## Goal

Manage remote data consistently.

## Requirements

- Query keys by domain
- Cache invalidation
- Pagination support
- Background refresh
- Optimistic updates only where safe
- Mutation error handling
- Polling for analysis status
- Stale-time strategy

## Definition of Done

- Duplicate API calls are reduced.
- Mutations update affected views.
- Analysis progress refreshes correctly.
- Cache does not leak between users or organizations.

---

# MODULE 8.3 — AUTHENTICATION INTEGRATION

## Goal

Connect frontend identity state to backend authentication.

## Requirements

- Login mutation
- Registration mutation
- Current-user query
- Refresh flow
- Logout
- Disabled-account handling
- Role and permission state
- Organization context

## Definition of Done

- Direct protected-route access works after refresh.
- Expired sessions recover or redirect safely.
- Logout clears cached sensitive data.

---

# MODULE 8.4 — REAL-TIME OR POLLED ANALYSIS STATUS

## Goal

Keep users informed while AI analysis runs.

## Initial Strategy

Use controlled polling if real-time infrastructure is not yet required.

Future options:

```text
WebSocket
Server-Sent Events
Message queue notifications
```

## Requirements

- Poll only while analysis is active.
- Stop polling on completion, failure or cancellation.
- Back off safely on temporary errors.
- Prevent excessive requests.
- Refresh incident summary after completion.

## Definition of Done

- Analysis progress updates automatically.
- Polling stops correctly.
- Browser resource usage remains reasonable.

---

# MODULE 8.5 — FILE-UPLOAD INTEGRATION

## Goal

Connect upload UI to backend validation and storage.

## Requirements

- Multipart requests
- Upload progress
- Cancellation where supported
- Validation-status refresh
- Duplicate-warning handling
- Retry support
- File deletion confirmation

## Definition of Done

- Upload and validation states remain synchronized.
- Failed uploads can be retried.
- File lists update without full reload.

---

# MODULE 8.6 — REPORT INTEGRATION

## Goal

Connect structured report data to preview and export functions.

## Requirements

- Generate report
- Poll generation status if asynchronous
- Display preview
- Download authorized output
- Preserve report versions
- Handle expired download links if used

## Definition of Done

- Report generation works end to end.
- Users can access only authorized reports.
- Version history is accurate.

---

# MODULE 8.7 — NOTIFICATION INTEGRATION

## Goal

Connect operational events to the notification interface.

## Requirements

- Fetch unread count
- Fetch notifications
- Mark as read
- Mark all as read
- Navigate to resource
- Refresh after key actions

## Definition of Done

- Notification state remains current.
- Invalid or unauthorized resource links fail safely.

---

# MODULE 8.8 — FRONTEND OBSERVABILITY

## Goal

Capture frontend failures and performance signals safely.

## Requirements

- Error boundary reporting
- API failure metrics
- Page-load timing
- Analysis-workspace timing
- Request ID correlation
- Safe user-context metadata
- No secrets or raw sensitive logs

## Definition of Done

- Frontend failures can be correlated with backend logs.
- Sensitive information is excluded.
- Development and production logging differ appropriately.

---

# 6. Frontend Testing Strategy

## Unit Tests

Test:

- Validation schemas
- Permission helpers
- Formatters
- State reducers or stores
- Query-key builders
- Error mapping

## Component Tests

Test:

- Forms
- Tables
- Modals
- Status badges
- Upload interface
- Analysis stepper
- Evidence viewer
- Recommendation cards
- Resolution form

## Integration Tests

Test:

- Login
- Project creation
- Incident creation
- File upload
- Start analysis
- View result
- Resolve incident
- Generate report

## End-to-End Tests

Critical flow:

```text
Register
    ↓
Login
    ↓
Create Project
    ↓
Create Incident
    ↓
Upload Files
    ↓
Start Analysis
    ↓
View Evidence
    ↓
Review Recommendations
    ↓
Resolve Incident
    ↓
Generate Report
```

## Accessibility Tests

- Automated accessibility scan
- Keyboard navigation
- Focus management
- Form-error announcement
- Modal and drawer behaviour

## Visual Regression

Recommended for:

- Application shell
- Dashboard
- Incident detail
- Analysis result
- Evidence viewer
- Reports

---

# 7. Performance Requirements

Targets should be validated on representative development and production environments.

Recommended goals:

```text
Initial protected-page load: acceptable under normal broadband
Route transition: near immediate when cached
Table interaction: responsive for expected dataset sizes
Analysis status update: timely without excessive polling
Large log viewer: virtualized where required
```

Optimization tasks:

- Route-level code splitting
- Lazy loading
- Memoization only where measured
- Table virtualization
- Deferred chart rendering
- Image optimization
- Bundle analysis
- Query caching
- Avoid unnecessary global state

---

# 8. Security Requirements

- Never render raw unsanitized HTML.
- Sanitize Markdown where supported.
- Do not expose internal file paths.
- Do not store passwords.
- Avoid storing long-lived sensitive tokens in insecure storage.
- Clear sensitive cache on logout.
- Enforce permissions in the backend even when the frontend hides actions.
- Protect downloadable report URLs.
- Redact secrets in displayed logs and evidence.
- Prevent cross-organization cache reuse.
- Apply Content Security Policy during deployment.
- Avoid exposing stack traces.

---

# 9. Documentation Deliverables

Create or update:

```text
UI_UX_DESIGN_SPECIFICATION.md
FRONTEND_ARCHITECTURE.md
DESIGN_SYSTEM.md
ROUTE_MAP.md
FRONTEND_API_INTEGRATION.md
ACCESSIBILITY_GUIDE.md
RESPONSIVE_DESIGN_GUIDE.md
FRONTEND_TESTING_GUIDE.md
ROLE_BASED_UI_MATRIX.md
ERROR_STATE_CATALOGUE.md
```

---

# 10. Part 4 Progress Tracker

| Module | Status | Progress |
|---|---|---:|
| 7.1 Design System | ⬜ Not Started | 0% |
| 7.2 Application Shell | ⬜ Not Started | 0% |
| 7.3 Routing and Guards | ⬜ Not Started | 0% |
| 7.4 Authentication UI | ⬜ Not Started | 0% |
| 7.5 Dashboard | ⬜ Not Started | 0% |
| 7.6 Project List | ⬜ Not Started | 0% |
| 7.7 Project Forms | ⬜ Not Started | 0% |
| 7.8 Project Detail | ⬜ Not Started | 0% |
| 7.9 Pipeline Runs | ⬜ Not Started | 0% |
| 7.10 Incident List | ⬜ Not Started | 0% |
| 7.11 Create Incident | ⬜ Not Started | 0% |
| 7.12 Incident Detail | ⬜ Not Started | 0% |
| 7.13 File Upload UI | ⬜ Not Started | 0% |
| 7.14 Analysis Workspace | ⬜ Not Started | 0% |
| 7.15 AI Analysis Result | ⬜ Not Started | 0% |
| 7.16 Evidence Viewer | ⬜ Not Started | 0% |
| 7.17 RAG Context Viewer | ⬜ Not Started | 0% |
| 7.18 Recommendations | ⬜ Not Started | 0% |
| 7.19 Timeline | ⬜ Not Started | 0% |
| 7.20 Notes | ⬜ Not Started | 0% |
| 7.21 Resolution | ⬜ Not Started | 0% |
| 7.22 Reports | ⬜ Not Started | 0% |
| 7.23 Analytics | ⬜ Not Started | 0% |
| 7.24 Notifications | ⬜ Not Started | 0% |
| 7.25 Profile and Security | ⬜ Not Started | 0% |
| 7.26 Organization Settings | ⬜ Not Started | 0% |
| 7.27 Admin Users | ⬜ Not Started | 0% |
| 7.28 Admin Models | ⬜ Not Started | 0% |
| 7.29 Admin Evaluation | ⬜ Not Started | 0% |
| 7.30 Audit Viewer | ⬜ Not Started | 0% |
| 7.31 Global Search | ⬜ Not Started | 0% |
| 7.32 Shared States | ⬜ Not Started | 0% |
| 7.33 Accessibility | ⬜ Not Started | 0% |
| 7.34 Responsive Design | ⬜ Not Started | 0% |
| 8.1 API Client | ⬜ Not Started | 0% |
| 8.2 Server State | ⬜ Not Started | 0% |
| 8.3 Authentication Integration | ⬜ Not Started | 0% |
| 8.4 Analysis Status | ⬜ Not Started | 0% |
| 8.5 File Integration | ⬜ Not Started | 0% |
| 8.6 Report Integration | ⬜ Not Started | 0% |
| 8.7 Notification Integration | ⬜ Not Started | 0% |
| 8.8 Frontend Observability | ⬜ Not Started | 0% |

---

# 11. Quality Gates

Part 4 cannot close until:

- [ ] Design system is implemented.
- [ ] Protected application shell works.
- [ ] Authentication flow works.
- [ ] Role-based navigation works.
- [ ] Dashboard uses live API data.
- [ ] Project workflows work.
- [ ] Incident workflows work.
- [ ] File upload and validation work.
- [ ] Analysis progress is visible.
- [ ] AI results are explainable.
- [ ] Evidence viewer links to source context.
- [ ] Recommendations can be reviewed.
- [ ] Resolution workflow works.
- [ ] Reports render correctly.
- [ ] Analytics work.
- [ ] Admin pages enforce permissions.
- [ ] Loading, empty and error states exist.
- [ ] Responsive review is complete.
- [ ] Accessibility review is complete.
- [ ] Unit tests pass.
- [ ] Component tests pass.
- [ ] Integration tests pass.
- [ ] End-to-end critical flow passes.
- [ ] No secrets appear in the browser console.
- [ ] Documentation is updated.
- [ ] No critical visual or functional defects remain.

---

# 12. Completion Criteria

Part 4 is complete when a user can successfully perform the complete interface-driven workflow:

```text
Register and Login
        ↓
Create or Select Organization
        ↓
Create Project
        ↓
Create Incident
        ↓
Upload and Validate Files
        ↓
Start AI Analysis
        ↓
Monitor Analysis Progress
        ↓
Review Classification
        ↓
Verify Evidence
        ↓
Review Retrieved Context
        ↓
Review Recommendations
        ↓
Add Human Notes
        ↓
Resolve Incident
        ↓
Generate and View Report
        ↓
View Analytics
```

The interface must be secure, responsive, accessible, testable and consistent with the approved DevGuard AI design system.

---

# 13. Next Roadmap Section

---

# Part 5

## Purpose

This part completes the DevGuard AI implementation roadmap by covering:
- End-to-end integration
- Research evaluation
- Deployment
- Monitoring and observability
- Security hardening
- Commercial SaaS roadmap

---

# Phase 8 — End-to-End Integration

Goal: Connect every completed module into one working platform.

Integration flow:

Authentication
→ Projects
→ Pipeline Runs
→ Incidents
→ File Upload
→ Dataset Pipeline
→ ML Classification
→ Evidence Extraction
→ RAG
→ LLM Reasoning
→ Recommendations
→ Reports
→ Analytics

Modules:
- API integration
- AI pipeline integration
- Frontend/backend validation
- Workflow validation
- Error handling

Definition of Done:
- Complete workflow executes successfully.
- No disconnected modules remain.
- API contracts are stable.

---

# Phase 9 — Research Evaluation

Goal: Validate the MSc research objectives.

Experiments:
- Rules-only baseline
- ML-only baseline
- LLM without RAG
- LLM with RAG
- Full DevGuard AI pipeline

Metrics:
- Accuracy
- Precision
- Recall
- F1 Score
- Top-K Accuracy
- Evidence Precision
- Retrieval Relevance
- Recommendation Usefulness
- MTTR Reduction
- End-to-End Latency

Deliverables:
- Evaluation report
- Charts
- Statistical analysis
- Dissertation figures

Definition of Done:
- Experiments completed.
- Results reproducible.
- Research questions answered.

---

# Phase 10 — Deployment

Goal: Deploy using cloud-native practices.

Pipeline:

GitHub
→ GitHub Actions
→ Docker Build
→ Container Registry
→ Cloud Deployment
→ Smoke Tests

Tasks:
- Multi-stage Docker builds
- CI/CD
- Environment management
- Rollback strategy
- Production configuration

Definition of Done:
- One-command deployment.
- Repeatable releases.
- Rollback documented.

---

# Phase 11 — Monitoring

Monitoring:
- API latency
- Error rate
- AI latency
- CPU
- Memory
- Database health

Logging:
- Structured logs
- Request IDs
- Correlation IDs

Alerting:
- High error rate
- Failed deployment
- Database unavailable

Definition of Done:
- Dashboards available.
- Alerts tested.
- Logs searchable.

---

# Phase 12 — Security

Tasks:
- HTTPS
- Secure headers
- Rate limiting
- Secret management
- Dependency scanning
- Container scanning
- Backup strategy

Security Tests:
- Authentication
- Authorization
- SQL Injection
- XSS
- File upload attacks
- Path traversal

Definition of Done:
- Security review completed.
- Critical vulnerabilities resolved.

---

# Phase 13 — Commercial SaaS Expansion

Future Features:
- Multi-tenancy
- Billing
- Subscription plans
- SSO
- Enterprise integrations
- Continuous learning
- Plugin marketplace
- Webhooks
- Executive dashboards

Definition of Done:
- SaaS roadmap documented.
- Architecture remains extensible.

---

# Final Testing

- Unit Tests
- Integration Tests
- End-to-End Tests
- Performance Tests
- Security Tests

---

# Final Documentation

- MASTER_ARCHITECTURE.md
- DATABASE_ARCHITECTURE.md
- AI_ARCHITECTURE.md
- API_SPECIFICATION.md
- UI_UX_DESIGN_SPECIFICATION.md
- DEPLOYMENT_GUIDE.md
- SECURITY_GUIDE.md
- TESTING_GUIDE.md
- USER_MANUAL.md

---

# Final Deliverables

- Complete source code
- Dataset
- Trained models
- AI pipeline
- Backend
- Frontend
- Docker
- CI/CD
- Evaluation report
- Dissertation artefacts
- Documentation

---

# Delivery Module Tracker (backend AI phases)

These delivery modules are tracked in project Cursor rules and are distinct from the
frontend “MODULE 8.x” screen work later in this roadmap.

| Delivery module | Status | Notes |
|---|---|---|
| Module 6 — Deterministic AI pipeline | ✅ Complete | Rules/hybrid classify → evidence → recommendations |
| Module 7 — Grounded RAG + LLM | ✅ Complete | Soft-fail retrieval/reasoning; deterministic fallback |
| Module 8 — Confidence/cost orchestration | ✅ Complete | Two-stage routing, budgets, fusion, evaluation metadata |
| Module 9 — Hybrid retrieval optimisation | ✅ Complete | embedding_only + hybrid_static + org-safe historical |
| Step 3 — Persistent Chroma (Docker) | ✅ Complete | chromadb/chroma:1.5.9 + HTTP client |
| Step 4 — Sentence-transformer embeddings | ✅ Complete | all-MiniLM-L6-v2 CPU + hash baseline preserved |
| Phase 1 — Dataset corpus kit | ✅ Complete | schemas, GitHub Issues API collector, dataset card (no full ingest / no GPT) |
| Phase 2 — Clean & normalise | ✅ Complete | spam/dedupe/mask filters → datasets/sanitized + phase2 report |
| Phase 3 — Extract knowledge | ✅ Complete | heuristic symptoms/cause/resolution → labelled + knowledge records |
| Phase 4–7 — Chunk/embed/eval/GPT | ✅ Complete | research Chroma collection + retrieval metrics + local/OpenAI diagnosis |
| Module 10 — Adaptive prompts / multi-agent | ⬜ Not started | Requires separate approval after Module 9 |

Module 9 research note: hybrid weights are heuristic and require experimental tuning.
Source authority is a boost, not a correctness guarantee. Historical incidents are used
only when resolved/trusted and organisation-scoped. Recency is not quality.
`embedding_only` remains the Module 7 baseline. Historical retrieval is disabled by default.

Step 4 note: `EMBEDDING_PROVIDER=hash` remains the deterministic default. Real local
embeddings use `sentence_transformers` + `all-MiniLM-L6-v2` on CPU. See
`docs/EMBEDDING_SETUP.md`. OpenAI reasoning is not part of Step 4.

---

# Production Checklist

- [ ] End-to-end integration complete
- [ ] Research evaluation complete
- [ ] Deployment validated
- [ ] Monitoring enabled
- [ ] Security review complete
- [ ] Documentation complete

---

# Roadmap Summary

Part 1 → Vision

Part 2 → Foundation & Core Platform

Part 3 → Dataset & AI

Part 4 → Frontend

Part 5 → Integration, Evaluation & Deployment
