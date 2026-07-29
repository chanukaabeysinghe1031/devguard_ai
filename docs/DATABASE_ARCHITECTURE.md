# DevGuard AI – DATABASE_ARCHITECTURE.md

**Version:** 1.0  
**Status:** Proposed Baseline  
**Architecture Style:** Incident-Centric Relational Data Model  
**Primary Database:** PostgreSQL  
**ORM:** SQLAlchemy  
**Migration Tool:** Alembic  

---

# 1. Purpose

This document defines the database architecture for DevGuard AI as an **AI-powered Incident Intelligence Platform**.

The database must support the complete operational flow:

```text
Organization
    ↓
User
    ↓
Project
    ↓
Pipeline Run
    ↓
Incident
    ↓
AI Analysis
    ↓
Evidence
    ↓
Recommendations
    ↓
Resolution
    ↓
Incident Report
    ↓
History and Analytics
```

The design must support the MSc prototype while remaining extensible for a future commercial SaaS platform.

---

# 2. Core Design Principles

The database design follows these principles:

1. **Incident-centered design**  
   The incident is the main operational entity of the platform.

2. **Clear separation of concerns**  
   Projects, pipeline executions, incidents, analyses, evidence, recommendations, reports and notifications are stored separately.

3. **Traceability**  
   Every AI-generated result must be traceable to its input files, model version, evidence and analysis run.

4. **Explainability**  
   Classifications, root-cause conclusions and recommendations must include confidence values and supporting evidence.

5. **Auditability**  
   Important user and system actions should be recorded.

6. **Extensibility**  
   The schema should support GitHub Actions first and later GitLab CI, Jenkins, Azure DevOps, Kubernetes and additional cloud providers.

7. **SaaS readiness**  
   The design includes organization and membership concepts so multi-tenant support can be added without redesigning the entire system.

8. **Soft deletion where appropriate**  
   Projects and selected business records should be archived instead of permanently deleted.

9. **Secure storage**  
   Secrets must not be stored in raw form. Sensitive values should be masked before persistence.

10. **Minimal duplication**  
    Reusable values such as failure categories and model versions should be normalized.

---

# 3. High-Level Entity Relationship Model

```text
organizations
    │
    ├── organization_members
    │       └── users
    │
    └── projects
            │
            ├── project_integrations
            ├── pipeline_runs
            │       │
            │       ├── uploaded_files
            │       └── incidents
            │               │
            │               ├── analysis_runs
            │               │       │
            │               │       ├── predictions
            │               │       ├── evidence_items
            │               │       ├── recommendations
            │               │       │       └── recommendation_steps
            │               │       └── retrieved_documents
            │               │
            │               ├── incident_events
            │               ├── incident_notes
            │               ├── incident_assignments
            │               ├── incident_resolutions
            │               ├── incident_reports
            │               ├── notifications
            │               └── feedback
            │
            └── analysis_history

model_versions
    ├── predictions
    └── evaluations

failure_categories
    └── predictions

knowledge_documents
    └── knowledge_chunks
            └── retrieved_documents

audit_logs
```

---

# 4. Main Domain Flow

```text
1. A user creates a project.
2. A pipeline execution is recorded.
3. A failure creates an incident.
4. Logs and configuration files are attached to the pipeline run or incident.
5. An analysis run is created.
6. The AI pipeline produces:
   - classification
   - confidence
   - evidence
   - retrieved documentation
   - root-cause explanation
   - recommendations (summary + recommendation_steps)
7. The engineer investigates and resolves the incident.
8. Resolution notes and time spent are recorded.
9. A report is generated.
10. The incident remains available in history and analytics.
```

---

# 5. Entity Specifications

## 5.1 organizations

Represents a company, team or workspace using DevGuard AI.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Organization identifier |
| name | VARCHAR(150) | NOT NULL | Organization name |
| slug | VARCHAR(120) | UNIQUE, NOT NULL | URL-safe identifier |
| plan | VARCHAR(50) | NOT NULL, DEFAULT `mvp` | Subscription or deployment plan |
| status | VARCHAR(30) | NOT NULL, DEFAULT `active` | active, suspended, archived |
| created_at | TIMESTAMPTZ | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL | Last update timestamp |
| archived_at | TIMESTAMPTZ | NULL | Archive timestamp |

### Notes

For the MSc MVP, the system may create one default organization automatically.

---

## 5.2 users

Represents authenticated platform users.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | User identifier |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Login email |
| password_hash | VARCHAR(255) | NOT NULL | Secure password hash |
| full_name | VARCHAR(150) | NOT NULL | User's name |
| avatar_url | TEXT | NULL | Profile image |
| is_platform_admin | BOOLEAN | NOT NULL, DEFAULT false | Platform-level admin (not an org membership role) |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Account status |
| last_login_at | TIMESTAMPTZ | NULL | Most recent login |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | Update time |

### Platform vs organization roles

- **`platform_admin`** is a **platform-level** capability on the user (`is_platform_admin` or equivalent). It is **not** stored as an `organization_members.role`.
- Organization-scoped roles live only on `organization_members` (see §5.3).
- There is **no `analyst` role** in the frozen v1.0 model. Legacy `analyst` values map to `engineer` on membership where needed.
- A legacy global `role` column (if retained temporarily during migration) must not be treated as the source of truth for org access.
---

## 5.3 organization_members

Links users to organizations.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Membership identifier |
| organization_id | UUID | FK, NOT NULL | Related organization |
| user_id | UUID | FK, NOT NULL | Related user |
| role | VARCHAR(40) | NOT NULL | Frozen org roles (see below) |
| joined_at | TIMESTAMPTZ | NOT NULL | Membership creation time |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Membership status |

### Frozen organization roles (v1.0)

| Role | Meaning |
|------|---------|
| `organization_owner` | Owns the organization; highest org privilege |
| `organization_admin` | Administers org settings and members |
| `engineer` | Day-to-day incident / pipeline work |
| `viewer` | Read-only access |

**Not used:** `analyst` (no analyst role in v1.0).  
**Not an org role:** `platform_admin` (platform-level on `users`, see §5.2).

### Constraints

```text
UNIQUE (organization_id, user_id)
```

---

## 5.4 projects

Represents a monitored software project or application.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Project identifier |
| organization_id | UUID | FK, NOT NULL | Owning organization |
| name | VARCHAR(150) | NOT NULL | Project name |
| key | VARCHAR(30) | NOT NULL | Short project key |
| description | TEXT | NULL | Project description |
| repository_url | TEXT | NULL | Source repository |
| default_branch | VARCHAR(120) | NULL | main, master or other branch |
| ci_provider | VARCHAR(50) | NOT NULL | github_actions, gitlab, jenkins |
| cloud_provider | VARCHAR(50) | NULL | aws, azure, gcp, none |
| default_environment | VARCHAR(50) | NULL | development, staging, production |
| status | VARCHAR(30) | NOT NULL, DEFAULT `active` | active, paused, archived |
| created_by | UUID | FK, NOT NULL | Creator |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | Update time |
| archived_at | TIMESTAMPTZ | NULL | Archive time |

### Constraints

```text
UNIQUE (organization_id, key)
```

---

## 5.5 project_integrations

Stores external integration metadata.

### Examples

- GitHub repository
- GitHub Actions webhook
- GitLab pipeline
- Jenkins server
- Slack workspace
- Microsoft Teams channel

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Integration identifier |
| project_id | UUID | FK, NOT NULL | Related project |
| provider | VARCHAR(60) | NOT NULL | github, gitlab, jenkins, slack |
| integration_type | VARCHAR(60) | NOT NULL | source_control, ci_cd, notification |
| external_reference | TEXT | NULL | Repository ID, workflow ID or channel ID |
| configuration | JSONB | NULL | Non-secret configuration |
| encrypted_secret_reference | TEXT | NULL | Reference to secret manager |
| status | VARCHAR(30) | NOT NULL | active, disabled, error |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | Update time |

### Security Rule

Actual access tokens should not be stored directly in plain text.

---

## 5.6 pipeline_runs

Represents one CI/CD workflow, deployment or infrastructure execution.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Pipeline run identifier |
| project_id | UUID | FK, NOT NULL | Related project |
| external_run_id | VARCHAR(255) | NULL | Provider's run ID |
| provider | VARCHAR(50) | NOT NULL | github_actions, gitlab, jenkins |
| workflow_name | VARCHAR(255) | NULL | Workflow or job name |
| branch | VARCHAR(255) | NULL | Branch name |
| commit_sha | VARCHAR(100) | NULL | Commit hash |
| triggered_by | VARCHAR(255) | NULL | User or system actor |
| environment | VARCHAR(50) | NULL | development, staging, production |
| status | VARCHAR(30) | NOT NULL | queued, running, succeeded, failed, cancelled |
| started_at | TIMESTAMPTZ | NULL | Execution start |
| completed_at | TIMESTAMPTZ | NULL | Execution end |
| duration_seconds | INTEGER | NULL | Execution duration |
| source_url | TEXT | NULL | Link to provider run |
| raw_metadata | JSONB | NULL | Provider-specific metadata |
| created_at | TIMESTAMPTZ | NOT NULL | Database creation time |

### Recommended indexes

```text
(project_id, created_at DESC)
(project_id, status)
(provider, external_run_id)
```

---

## 5.7 incidents

Represents the central operational object.

An incident is created when a pipeline fails, an engineer uploads failure artifacts, or an integration detects a deployment problem.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Incident identifier |
| incident_number | BIGINT | UNIQUE, NOT NULL | Human-readable sequential number |
| project_id | UUID | FK, NOT NULL | Related project |
| pipeline_run_id | UUID | FK, NULL | Related pipeline run |
| title | VARCHAR(255) | NOT NULL | Incident title |
| description | TEXT | NULL | User or system description |
| source | VARCHAR(40) | NOT NULL | manual_upload, webhook, api, system |
| status | VARCHAR(40) | NOT NULL | detected, analysing, open, in_progress, resolved, closed |
| severity | VARCHAR(20) | NOT NULL | critical, high, medium, low |
| priority | VARCHAR(20) | NULL | urgent, high, normal, low |
| environment | VARCHAR(50) | NULL | Affected environment |
| detected_at | TIMESTAMPTZ | NOT NULL | Initial detection |
| acknowledged_at | TIMESTAMPTZ | NULL | First acknowledgement |
| resolved_at | TIMESTAMPTZ | NULL | Resolution time |
| closed_at | TIMESTAMPTZ | NULL | Closure time |
| created_by | UUID | FK, NULL | User who created manually |
| current_assignee_id | UUID | FK, NULL | Current responsible user |
| latest_analysis_run_id | UUID | NULL | Latest successful analysis reference |
| root_cause_summary | TEXT | NULL | Confirmed or accepted root cause |
| impact_summary | TEXT | NULL | Business or technical impact |
| tags | JSONB | NULL | Flexible incident tags |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | Last update time |

### Recommended status transitions

```text
detected
    ↓
analysing
    ↓
open
    ↓
in_progress
    ↓
resolved
    ↓
closed
```

Alternative statuses:

- analysis_failed
- ignored
- false_positive
- reopened

### Recommended indexes

```text
(project_id, created_at DESC)
(project_id, status)
(severity, status)
(current_assignee_id, status)
(detected_at DESC)
```

---

## 5.8 uploaded_files

Stores metadata for logs, configuration files and archives submitted for analysis.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | File identifier |
| user_id | UUID | FK, NOT NULL | Uploader |
| project_id | UUID | FK, NOT NULL | Related project |
| pipeline_run_id | UUID | FK, NULL | Related pipeline run |
| incident_id | UUID | FK, NULL | Related incident |
| original_filename | VARCHAR(255) | NOT NULL | Original name |
| stored_filename | VARCHAR(255) | NOT NULL | Internal storage name |
| storage_path | TEXT | NOT NULL | Object or local storage location |
| file_type | VARCHAR(50) | NOT NULL | log, yaml, terraform, json, zip |
| mime_type | VARCHAR(150) | NULL | MIME type |
| size_bytes | BIGINT | NOT NULL | File size |
| checksum_sha256 | VARCHAR(64) | NOT NULL | Integrity and duplicate check |
| secret_masking_status | VARCHAR(30) | NOT NULL | pending, completed, failed |
| validation_status | VARCHAR(30) | NOT NULL | pending, valid, invalid |
| processing_status | VARCHAR(30) | NOT NULL | uploaded, processing, processed, failed |
| extracted_metadata | JSONB | NULL | Parsed metadata |
| uploaded_at | TIMESTAMPTZ | NOT NULL | Upload time |

### Rules

- Raw secrets must be masked before analysis.
- Duplicate checks may use `checksum_sha256`.
- Large raw files may be stored outside PostgreSQL.
- The database should store metadata and references, not large binary content.

---

## 5.9 analysis_runs

Represents one execution of the complete AI pipeline.

This is separate from the incident so an incident can be analyzed multiple times.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Analysis run identifier |
| incident_id | UUID | FK, NOT NULL | Related incident |
| pipeline_run_id | UUID | FK, NULL | Related pipeline run |
| requested_by | UUID | FK, NULL | User or system |
| status | VARCHAR(30) | NOT NULL | queued, preprocessing, classifying, retrieving, reasoning, completed, failed |
| analysis_type | VARCHAR(40) | NOT NULL | full, reanalysis, classification_only |
| started_at | TIMESTAMPTZ | NULL | Start time |
| completed_at | TIMESTAMPTZ | NULL | Completion time |
| duration_ms | BIGINT | NULL | Total processing time |
| current_stage | VARCHAR(60) | NULL | Active AI pipeline stage |
| progress_percentage | SMALLINT | NOT NULL, DEFAULT 0 | User-visible progress |
| input_summary | JSONB | NULL | Files and pipeline metadata |
| output_summary | JSONB | NULL | Final structured result |
| error_code | VARCHAR(100) | NULL | Failure code |
| error_message | TEXT | NULL | Safe technical error |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

### Recommended indexes

```text
(incident_id, created_at DESC)
(status, created_at)
```

---

## 5.10 failure_categories

Stores normalized failure classes.

### Example categories

- dependency_failure
- test_failure
- build_failure
- authentication_failure
- authorization_failure
- network_failure
- configuration_failure
- terraform_validation_failure
- terraform_plan_failure
- infrastructure_permission_failure
- deployment_failure
- container_failure

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Category identifier |
| code | VARCHAR(100) | UNIQUE, NOT NULL | Stable category code |
| name | VARCHAR(150) | NOT NULL | Display name |
| description | TEXT | NULL | Category definition |
| parent_id | UUID | FK, NULL | Optional hierarchy |
| default_severity | VARCHAR(20) | NULL | Default severity |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Availability |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

---

## 5.11 predictions

Stores structured classification and root-cause prediction results.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Prediction identifier |
| analysis_run_id | UUID | FK, NOT NULL | Related analysis |
| failure_category_id | UUID | FK, NOT NULL | Predicted category |
| model_version_id | UUID | FK, NOT NULL | Model used |
| confidence | NUMERIC(5,4) | NOT NULL | Value from 0 to 1 |
| rank | SMALLINT | NOT NULL, DEFAULT 1 | Top-k position |
| predicted_label | VARCHAR(150) | NOT NULL | Model output label |
| root_cause_summary | TEXT | NULL | AI-generated root cause |
| technical_explanation | TEXT | NULL | Detailed explanation |
| impact_summary | TEXT | NULL | Estimated impact |
| reasoning_metadata | JSONB | NULL | Structured AI metadata |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

### Constraints

```text
CHECK (confidence >= 0 AND confidence <= 1)
UNIQUE (analysis_run_id, rank)
```

---

## 5.12 evidence_items

Stores supporting evidence extracted from uploaded files and logs.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Evidence identifier |
| analysis_run_id | UUID | FK, NOT NULL | Related analysis |
| prediction_id | UUID | FK, NULL | Related prediction |
| uploaded_file_id | UUID | FK, NULL | Source file |
| evidence_type | VARCHAR(50) | NOT NULL | error, warning, stack_trace, config, permission |
| source_name | VARCHAR(255) | NULL | File or source name |
| line_start | INTEGER | NULL | Starting line |
| line_end | INTEGER | NULL | Ending line |
| raw_excerpt | TEXT | NULL | Masked evidence excerpt |
| normalized_excerpt | TEXT | NULL | Cleaned evidence |
| explanation | TEXT | NULL | Why it matters |
| importance_score | NUMERIC(5,4) | NULL | Relevance score |
| metadata | JSONB | NULL | Parser-specific details |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

### Security Requirement

Only masked and sanitized excerpts should be stored.

---

## 5.13 recommendations

Parent/summary record for AI remediation guidance produced by an analysis run.

Ordered steps are **not** stored as columns on this table. Steps belong in **`recommendation_steps`** (§5.13a). Legacy JSON remediation blobs (`remediation_steps`, `preventive_actions`, `future_improvements`, and similar) are **not** the source of truth.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Recommendation identifier |
| analysis_run_id | UUID | FK, NOT NULL | Related analysis |
| prediction_id | UUID | FK, NULL | Related prediction |
| root_cause | TEXT | NULL | Optional summary root cause |
| explanation | TEXT | NULL | Optional summary explanation |
| llm_model | VARCHAR(100) | NULL | Model used to generate guidance |
| confidence | NUMERIC(5,4) | NULL | Overall confidence (0–1) |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| updated_at | TIMESTAMPTZ | NULL | Last update time |

### Notes

- One recommendation summary may own many `recommendation_steps`.
- Do not use `step_number` on this table as the primary step model.
- Query patterns that need steps should join `recommendation_steps` (and may also filter by denormalized `analysis_run_id` on steps).

---

## 5.13a recommendation_steps

Normalized ordered remediation, verification, and prevention steps for a recommendation.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Step identifier |
| recommendation_id | UUID | FK, NOT NULL | Parent recommendation summary |
| analysis_run_id | UUID | FK, NOT NULL | Denormalized analysis run for query convenience |
| step_number | INTEGER | NOT NULL | Order within the recommendation |
| step_type | VARCHAR(30) | NOT NULL | `remediation` \| `verification` \| `prevention` |
| title | VARCHAR(255) | NOT NULL | Action title |
| action | TEXT | NOT NULL | Recommended action |
| explanation | TEXT | NULL | Why the action is required |
| expected_result | TEXT | NULL | Expected outcome |
| risk_level | VARCHAR(20) | NULL | low, medium, high |
| difficulty | VARCHAR(20) | NULL | easy, moderate, advanced |
| command_template | TEXT | NULL | Safe command template if appropriate |
| accepted | BOOLEAN | NULL | User acceptance |
| completed | BOOLEAN | NOT NULL, DEFAULT false | Completion state |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

### Constraints

```text
UNIQUE (recommendation_id, step_number)
```

### Notes

- `step_type` is restricted to `remediation`, `verification`, or `prevention`.
- Both `recommendation_id` and `analysis_run_id` are stored to support parent-scoped and analysis-scoped query patterns.
- This table is the durable source of truth for step content; do not rely on legacy JSON blobs on `recommendations`.

---

## 5.14 knowledge_documents

Represents official documentation stored for RAG.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Document identifier |
| provider | VARCHAR(60) | NOT NULL | github, terraform, aws, docker |
| title | VARCHAR(255) | NOT NULL | Document title |
| source_url | TEXT | NULL | Original source |
| version | VARCHAR(100) | NULL | Documentation version |
| content_hash | VARCHAR(64) | NULL | Change detection |
| status | VARCHAR(30) | NOT NULL | active, outdated, archived |
| ingested_at | TIMESTAMPTZ | NOT NULL | Ingestion time |
| updated_at | TIMESTAMPTZ | NOT NULL | Update time |

---

## 5.15 knowledge_chunks

Stores retrievable documentation segments.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Chunk identifier |
| document_id | UUID | FK, NOT NULL | Parent document |
| chunk_index | INTEGER | NOT NULL | Order |
| heading | TEXT | NULL | Section heading |
| content | TEXT | NOT NULL | Chunk content |
| token_count | INTEGER | NULL | Approximate token count |
| embedding_reference | TEXT | NULL | ChromaDB or vector reference |
| metadata | JSONB | NULL | Provider, service, tags |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

### Note

Embeddings may remain in ChromaDB while PostgreSQL stores the durable metadata and references.

---

## 5.16 retrieved_documents

Stores which knowledge chunks were used during analysis.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Retrieval record |
| analysis_run_id | UUID | FK, NOT NULL | Related analysis |
| knowledge_chunk_id | UUID | FK, NOT NULL | Retrieved chunk |
| rank | INTEGER | NOT NULL | Retrieval order |
| similarity_score | NUMERIC(7,6) | NULL | Retrieval score |
| used_in_reasoning | BOOLEAN | NOT NULL, DEFAULT true | Whether included in LLM context |
| created_at | TIMESTAMPTZ | NOT NULL | Retrieval time |

### Importance

This table provides citation and grounding traceability.

---

## 5.17 incident_events

Stores the chronological incident timeline.

### Event examples

- incident_created
- analysis_started
- classification_completed
- recommendation_generated
- assigned
- status_changed
- note_added
- resolved
- reopened
- report_generated

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Event identifier |
| incident_id | UUID | FK, NOT NULL | Related incident |
| event_type | VARCHAR(80) | NOT NULL | Event code |
| actor_type | VARCHAR(20) | NOT NULL | user, system, ai |
| actor_user_id | UUID | FK, NULL | User actor |
| title | VARCHAR(255) | NOT NULL | Timeline title |
| description | TEXT | NULL | Event details |
| metadata | JSONB | NULL | Structured details |
| occurred_at | TIMESTAMPTZ | NOT NULL | Event time |

### Recommended index

```text
(incident_id, occurred_at)
```

---

## 5.18 incident_notes

Stores investigation and collaboration notes.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Note identifier |
| incident_id | UUID | FK, NOT NULL | Related incident |
| author_id | UUID | FK, NOT NULL | Note author |
| note_type | VARCHAR(30) | NOT NULL | investigation, resolution, internal |
| content | TEXT | NOT NULL | Note content |
| is_pinned | BOOLEAN | NOT NULL, DEFAULT false | Pinned state |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |
| updated_at | TIMESTAMPTZ | NOT NULL | Update time |

---

## 5.19 incident_assignments

Stores assignment history.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Assignment identifier |
| incident_id | UUID | FK, NOT NULL | Related incident |
| assigned_to | UUID | FK, NOT NULL | Assigned user |
| assigned_by | UUID | FK, NULL | Assigning user or system |
| assigned_at | TIMESTAMPTZ | NOT NULL | Assignment time |
| unassigned_at | TIMESTAMPTZ | NULL | End of assignment |
| reason | TEXT | NULL | Assignment reason |

---

## 5.20 incident_resolutions

Stores structured resolution information.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Resolution identifier |
| incident_id | UUID | FK, NOT NULL | Related incident |
| resolved_by | UUID | FK, NOT NULL | Resolving user |
| resolution_summary | TEXT | NOT NULL | Final resolution |
| confirmed_root_cause | TEXT | NOT NULL | Confirmed cause |
| resolution_steps | JSONB | NULL | Steps performed |
| prevention_actions | JSONB | NULL | Future prevention |
| time_spent_minutes | INTEGER | NULL | Human effort |
| AI_recommendation_used | BOOLEAN | NULL | Whether AI guidance helped |
| created_at | TIMESTAMPTZ | NOT NULL | Resolution time |

### MVP Rule

Normally one active resolution record exists per resolved incident. Reopened incidents may receive additional resolution records.

---

## 5.21 incident_reports

Stores generated incident report metadata.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Report identifier |
| incident_id | UUID | FK, NOT NULL | Related incident |
| generated_by | UUID | FK, NULL | User or system |
| format | VARCHAR(20) | NOT NULL | pdf, markdown, json |
| version | INTEGER | NOT NULL, DEFAULT 1 | Report version |
| storage_path | TEXT | NOT NULL | Generated file location |
| checksum_sha256 | VARCHAR(64) | NULL | File integrity |
| generation_status | VARCHAR(30) | NOT NULL | queued, completed, failed |
| created_at | TIMESTAMPTZ | NOT NULL | Generation time |

---

## 5.22 notifications

Stores user notifications related to incidents and analyses.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Notification identifier |
| user_id | UUID | FK, NOT NULL | Recipient |
| incident_id | UUID | FK, NULL | Related incident |
| notification_type | VARCHAR(60) | NOT NULL | incident_created, analysis_complete, critical_failure |
| title | VARCHAR(255) | NOT NULL | Notification title |
| message | TEXT | NOT NULL | Notification body |
| severity | VARCHAR(20) | NULL | critical, warning, info, success |
| channel | VARCHAR(30) | NOT NULL | in_app, email, slack, teams |
| delivery_status | VARCHAR(30) | NOT NULL | pending, sent, failed |
| is_read | BOOLEAN | NOT NULL, DEFAULT false | Read state |
| sent_at | TIMESTAMPTZ | NULL | Delivery time |
| read_at | TIMESTAMPTZ | NULL | Read time |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

### Recommended indexes

```text
(user_id, is_read, created_at DESC)
(incident_id)
```

---

## 5.23 feedback

Stores user evaluation of AI output.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Feedback identifier |
| user_id | UUID | FK, NOT NULL | User |
| incident_id | UUID | FK, NOT NULL | Incident |
| analysis_run_id | UUID | FK, NOT NULL | Analysis |
| prediction_id | UUID | FK, NULL | Prediction |
| recommendation_id | UUID | FK, NULL | Recommendation |
| feedback_type | VARCHAR(40) | NOT NULL | classification, evidence, recommendation, overall |
| rating | SMALLINT | NULL | 1 to 5 |
| is_correct | BOOLEAN | NULL | Correctness |
| is_useful | BOOLEAN | NULL | Usefulness |
| comment | TEXT | NULL | Qualitative feedback |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

### Constraints

```text
CHECK (rating IS NULL OR rating BETWEEN 1 AND 5)
```

---

## 5.24 model_versions

Stores reproducible model information.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Model version identifier |
| model_name | VARCHAR(150) | NOT NULL | Model name |
| model_type | VARCHAR(50) | NOT NULL | classifier, embedding, llm |
| version | VARCHAR(100) | NOT NULL | Version |
| provider | VARCHAR(100) | NULL | local, openai, sentence_transformers |
| artifact_path | TEXT | NULL | Model artifact |
| training_dataset_version | VARCHAR(100) | NULL | Dataset reference |
| configuration | JSONB | NULL | Hyperparameters |
| metrics | JSONB | NULL | Accuracy, F1, top-k and related metrics |
| status | VARCHAR(30) | NOT NULL | training, active, inactive, failed |
| trained_at | TIMESTAMPTZ | NULL | Training time |
| created_at | TIMESTAMPTZ | NOT NULL | Creation time |

### Constraints

```text
UNIQUE (model_name, version)
```

---

## 5.25 evaluations

Stores formal MSc and operational evaluation results.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Evaluation identifier |
| model_version_id | UUID | FK, NOT NULL | Evaluated model |
| evaluation_type | VARCHAR(60) | NOT NULL | classification, evidence, usefulness, mttr |
| dataset_version | VARCHAR(100) | NULL | Dataset used |
| metric_name | VARCHAR(100) | NOT NULL | accuracy, macro_f1, top_k, precision |
| metric_value | NUMERIC(12,6) | NOT NULL | Metric value |
| sample_size | INTEGER | NULL | Number of evaluated samples |
| metadata | JSONB | NULL | Experiment details |
| evaluated_at | TIMESTAMPTZ | NOT NULL | Evaluation time |

---

## 5.26 analysis_history

Provides a user-facing history index.

This table is optional because history may be derived from incidents and analysis runs. It is useful if denormalized history improves performance.

### Recommended Approach

For the MVP, do not create a separate history table unless a clear need appears.

Instead, generate history from:

- incidents
- analysis_runs
- pipeline_runs
- incident_resolutions
- predictions

A PostgreSQL materialized view may be introduced later.

---

## 5.27 audit_logs

Stores important security and administrative actions.

### Columns

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK | Audit identifier |
| organization_id | UUID | FK, NULL | Related organization |
| user_id | UUID | FK, NULL | Actor |
| action | VARCHAR(100) | NOT NULL | login, project_update, incident_resolved |
| resource_type | VARCHAR(80) | NULL | user, project, incident, report |
| resource_id | UUID | NULL | Related record |
| ip_address | INET | NULL | Source IP |
| user_agent | TEXT | NULL | Client details |
| metadata | JSONB | NULL | Additional details |
| created_at | TIMESTAMPTZ | NOT NULL | Action time |

### Rule

Audit records should be append-only.

---

# 6. Relationship Summary

| Parent | Relationship | Child |
|---|---|---|
| Organization | 1:N | Projects |
| Organization | M:N through membership | Users |
| Project | 1:N | Pipeline Runs |
| Project | 1:N | Incidents |
| Pipeline Run | 1:N | Uploaded Files |
| Pipeline Run | 1:N | Incidents |
| Incident | 1:N | Analysis Runs |
| Incident | 1:N | Events |
| Incident | 1:N | Notes |
| Incident | 1:N | Reports |
| Incident | 1:N | Notifications |
| Analysis Run | 1:N | Predictions |
| Analysis Run | 1:N | Evidence |
| Analysis Run | 1:N | Recommendations |
| Analysis Run | 1:N | Retrieved Documents |
| Failure Category | 1:N | Predictions |
| Model Version | 1:N | Predictions |
| Knowledge Document | 1:N | Knowledge Chunks |
| Knowledge Chunk | 1:N | Retrieved Documents |

---

# 7. Deletion and Cascade Strategy

## Hard delete

Suitable only for:

- temporary failed upload records
- test data
- incomplete records with no business history

## Soft delete or archive

Recommended for:

- organizations
- users
- projects
- integrations

## Restricted delete

An incident should not be deleted if it contains:

- analysis results
- reports
- audit-relevant activity
- formal research evaluation data

## Suggested foreign-key behaviour

| Relationship | Behaviour |
|---|---|
| Organization → Projects | RESTRICT |
| Project → Incidents | RESTRICT |
| Incident → Analysis Runs | CASCADE only in test environments |
| Analysis Run → Evidence | CASCADE |
| Analysis Run → Recommendations | CASCADE |
| Incident → Reports | RESTRICT |
| User → Notes | RESTRICT or anonymize |

---

# 8. PostgreSQL Features

Recommended PostgreSQL features:

- UUID primary keys
- JSONB for provider-specific metadata
- GIN indexes for searchable JSONB tags
- Full-text search for incident titles and root-cause summaries
- Partial indexes for open incidents
- Materialized views for analytics
- Row-level security in a future SaaS version

### Example partial index

```sql
CREATE INDEX ix_incidents_open
ON incidents (project_id, severity, detected_at DESC)
WHERE status IN ('detected', 'analysing', 'open', 'in_progress');
```

### Example full-text index

```sql
CREATE INDEX ix_incidents_search
ON incidents
USING GIN (
    to_tsvector(
        'english',
        coalesce(title, '') || ' ' ||
        coalesce(description, '') || ' ' ||
        coalesce(root_cause_summary, '')
    )
);
```

---

# 9. Current Schema Mapping

The existing project already contains these tables:

- users
- uploaded_files
- pipeline_run
- failure_category
- prediction
- evidence_item
- recommendation
- model_version
- evaluation
- feedback
- analysis_history

These should not be discarded. They should be evolved.

| Current Table | Target Table | Required Change |
|---|---|---|
| users | users | Keep and extend |
| uploaded_files | uploaded_files | Add project, incident and pipeline references |
| pipeline_run | pipeline_runs | Rename consistently and extend |
| failure_category | failure_categories | Rename consistently |
| prediction | predictions | Link to analysis_run |
| evidence_item | evidence_items | Link to analysis_run and source file |
| recommendation | recommendations + recommendation_steps | Link summary to analysis_run; store ordered steps in recommendation_steps |
| model_version | model_versions | Extend metadata |
| evaluation | evaluations | Extend experiment details |
| feedback | feedback | Link to incident and analysis |
| analysis_history | Derived view or archive | Reassess necessity |

### New core tables

- organizations
- organization_members
- projects
- project_integrations
- incidents
- analysis_runs
- incident_events
- incident_notes
- incident_assignments
- incident_resolutions
- incident_reports
- notifications
- knowledge_documents
- knowledge_chunks
- retrieved_documents
- recommendation_steps
- audit_logs

---

# 10. Recommended Migration Plan

## Migration 002 – Organization and Project Foundation

Create:

- organizations
- organization_members
- projects
- project_integrations

Update:

- users

Seed (idempotent script + env vars, not Alembic):

- one default organization
- one default `organization_owner` membership
- platform admin flag when required

---

## Migration 003 – Incident Domain

Create:

- incidents
- incident_events
- incident_notes
- incident_assignments
- incident_resolutions

Update:

- pipeline_runs
- uploaded_files

---

## Migration 004 – AI Analysis Runs

Create:

- analysis_runs
- retrieved_documents
- recommendation_steps

Update:

- predictions
- evidence_items
- recommendations (parent/summary; steps moved to recommendation_steps)
- feedback

Deprecate:

- analysis_history (drop in Migration 007)

---

## Migration 005 – Reporting and Notifications

Create:

- incident_reports
- notifications
- audit_logs

---

## Migration 006 – Knowledge Base Metadata

Create:

- knowledge_documents
- knowledge_chunks

---

## Migration 007 – Indexes and Constraints

Add:

- partial indexes
- search indexes
- unique constraints
- check constraints
- cascade rules

Cleanup:

- drop `analysis_history`
- drop obsolete recommendation JSON blob columns

---

# 11. MVP Database Scope

The MSc MVP should prioritize the following tables:

## Required

- users
- projects
- pipeline_runs
- incidents
- uploaded_files
- analysis_runs
- failure_categories
- predictions
- evidence_items
- recommendations
- recommendation_steps
- incident_events
- incident_resolutions
- incident_reports
- notifications
- model_versions
- evaluations
- feedback

## Optional for MVP

- organizations
- organization_members
- project_integrations
- incident_assignments
- incident_notes
- knowledge_documents
- knowledge_chunks
- retrieved_documents
- audit_logs

Even if optional tables are not fully implemented, the architecture should preserve a clear path to them.

---

# 12. Suggested MVP Simplification

To avoid unnecessary complexity during the MSc implementation:

1. Create one default organization.
2. Support one owner per project.
3. Use only in-app notifications.
4. Store generated reports on the local filesystem or object storage.
5. Keep ChromaDB embeddings outside PostgreSQL.
6. Keep one active classifier model.
7. Allow multiple analysis runs per incident.
8. Support only GitHub Actions and Terraform initially.
9. Derive history from incidents instead of maintaining a separate history table.
10. Keep team assignment features minimal.

---

# 13. Example Incident Record Flow

```text
Project:
DevGuard API

Pipeline Run:
GitHub Actions Run #485

Incident:
INC-000145
Production deployment failed

Uploaded Files:
github-actions.log
main.tf
deploy.yml

Analysis Run:
Full AI analysis

Prediction:
Infrastructure Permission Failure
Confidence: 0.94

Evidence:
"AccessDenied: User is not authorized to perform ecs:UpdateService"

Recommendation:
Update the IAM deployment role with the required ECS permission.

Resolution:
IAM policy updated and workflow rerun successfully.

Report:
INC-000145.pdf
```

---

# 14. Data Retention Recommendations

## Raw uploaded files

- MVP: configurable retention
- Suggested default: 30 to 90 days
- Delete earlier when users request removal

## Incident metadata

- Retain for long-term history

## AI analysis results

- Retain for explainability and evaluation

## Reports

- Retain until explicitly deleted or archived

## Audit logs

- Retain according to organizational policy

## Masked evidence

- Retain with the incident
- Never retain exposed secrets

---

# 15. Security Requirements

1. Hash passwords using Argon2 or bcrypt.
2. Never store raw passwords.
3. Mask secrets before storing evidence.
4. Encrypt sensitive integration configuration.
5. Store external credentials in a secret manager.
6. Apply organization filtering to every tenant-owned query.
7. Record security-sensitive actions in audit logs.
8. Use parameterized queries through SQLAlchemy.
9. Validate uploaded file types and sizes.
10. Restrict report and artifact access to authorized users.

---

# 16. Analytics Supported by This Design

The schema supports:

- Open incidents by severity
- Incidents by project
- Failure categories over time
- Deployment success and failure rates
- Mean time to acknowledge
- Mean time to resolve
- AI confidence distribution
- Recommendation usefulness
- Root-cause accuracy
- Repeated incident categories
- Model performance by version
- User feedback trends
- Incidents resolved using AI recommendations

---

# 17. Final Recommended Architecture

The primary relationship chain should be:

```text
User
  ↓
Project
  ↓
Pipeline Run
  ↓
Incident
  ↓
Analysis Run
  ├── Prediction
  ├── Evidence
  ├── Retrieved Documentation
  └── Recommendations
  ↓
Resolution
  ↓
Report
```

The **Incident** is the main business object.

The **Analysis Run** is the main AI execution object.

This separation is essential because:

- one incident may be analyzed more than once
- different model versions may be compared
- failed analyses can be retried
- AI output can evolve without changing incident history
- research evaluation becomes reproducible

---

# 18. Architecture Decision

DevGuard AI will use an **incident-centric PostgreSQL data model**.

The database will:

- preserve the existing AI entities
- introduce projects and incidents
- separate incidents from AI analysis runs
- retain evidence and model traceability
- support resolution and reporting workflows
- remain compatible with future SaaS and integration requirements

This architecture should be treated as the baseline before implementing the next backend modules.
