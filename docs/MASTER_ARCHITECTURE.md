# DevGuard AI — Master Architecture Document

**Version:** 1.1  
**Status:** ARCHITECTURE FROZEN FOR IMPLEMENTATION  
**Project Type:** MSc Advanced Software Engineering Dissertation + Commercial SaaS Foundation  
**Last Updated:** July 2026

---

# 1. Document Authority

This document is the **single source of truth** for DevGuard AI.

Every architectural decision must follow this document.

All other project documents extend this document. When two documents conflict, the following authority order applies:

1. `MASTER_ARCHITECTURE.md`
2. `PROJECT_CONSTITUTION.md`
3. `PROJECT_STRUCTURE.md`
4. `DATABASE_ARCHITECTURE.md`
5. `API_SPECIFICATION.md`
6. `AI_ARCHITECTURE.md`
7. `DATASET_SPECIFICATION.md`
8. Screen and workflow specifications
9. `IMPLEMENTATION_ROADMAP.md`
10. UI prompt collection

No implementation tool, developer, or AI coding assistant may override this order.

---

# 2. Project Vision

DevGuard AI is an AI-powered DevOps Incident Intelligence Platform.

It analyses CI/CD failures, Infrastructure-as-Code artifacts, deployment configurations, and related operational evidence to:

- classify failures;
- identify the affected pipeline stage and component;
- extract supporting evidence;
- retrieve relevant technical knowledge;
- generate grounded root-cause explanations;
- generate remediation and prevention recommendations;
- support the complete incident lifecycle;
- evaluate AI accuracy, grounding, usefulness, and operational value.

The project has two objectives:

1. Successfully complete an MSc Advanced Software Engineering dissertation.
2. Establish a production-quality foundation for a future commercial SaaS platform.

Every implementation decision must support the MSc scope without blocking future commercial evolution.

---

# 3. Product Positioning

DevGuard AI is not merely a log analyser.

It is an incident-centred AI assistant that helps software engineers and DevOps professionals answer:

1. What failed?
2. Where did it fail?
3. Why did it fail?
4. What evidence supports the conclusion?
5. How confident is the system?
6. What should the engineer do next?
7. How can the failure be prevented?

The system recommends actions. It does not automatically modify infrastructure, execute remediation commands, alter IAM policies, or rerun production deployments during the MSc MVP.

---

# 4. Version Strategy

## 4.1 Version 1.0 — MSc MVP

### Supported Platforms

- GitHub Actions
- Terraform
- AWS-related deployment failures
- Generic CI/CD build, test, dependency, configuration, and deployment logs

### Input Method

- Manual project creation
- Manual incident creation or draft-incident creation through the upload wizard
- Manual artifact upload

### Required AI Features

- File validation
- Secret detection and masking
- Log and configuration parsing
- Metadata extraction
- Rule-based classification
- TF-IDF feature extraction
- Logistic Regression baseline classifier
- Top-k predictions
- Evidence extraction
- Sentence Transformer embeddings
- ChromaDB retrieval
- LLM root-cause reasoning
- Structured recommendations
- Confidence scoring
- Model and prompt versioning
- User feedback
- Research evaluation

### Required Frontend

- Login
- Dashboard
- Projects
- Create Incident / Upload Wizard
- Analysis Progress
- Incident Details
- Evidence Viewer
- Recommendation Viewer
- Resolution
- History
- Reports
- Evaluation
- Basic Profile and Security Settings

### Required Backend

- FastAPI REST API
- PostgreSQL
- SQLAlchemy
- Alembic
- ChromaDB
- File storage abstraction
- Authentication and authorization
- Incident workflow
- Analysis orchestration
- Report generation
- In-app notifications

### MSc MVP Organization Model

Version 1.0 will include a **minimal organization-ready model**:

- one default organization is created automatically;
- each user belongs to the default organization;
- tenant-owned records include `organization_id`;
- organization-scoped authorization is enforced;
- one organization owner role is supported;
- organization switching, invitations, billing, and advanced team management are deferred.

This provides data isolation and future SaaS readiness without implementing full commercial multi-tenancy.

---

## 4.2 Version 2.0 — Provider Expansion

Future additions:

- GitLab CI
- Jenkins
- Azure DevOps
- Docker analysis
- Kubernetes analysis
- Automated GitHub webhook ingestion
- CloudWatch and other monitoring-source ingestion

---

## 4.3 Version 3.0 — Commercial Multi-Tenant SaaS

Future additions:

- multiple organizations per user;
- organization switching;
- invitations;
- team collaboration;
- enterprise roles;
- billing;
- subscriptions;
- usage limits;
- SSO and SAML;
- Slack, Teams, and email notifications;
- audit export;
- API keys and webhooks.

---

## 4.4 Version 4.0 — Intelligent Automation

Future additions:

- AI DevOps Copilot;
- predictive deployment risk;
- incident similarity search;
- continuous learning;
- automated recommendation ranking;
- approved self-healing workflows;
- human-governed remediation automation.

---

# 5. Architectural Style

DevGuard AI will be implemented as a **modular monolith** for the MSc MVP.

Microservices must not be introduced unless operational scale or independent deployment requirements justify their complexity.

The architecture follows:

- Clean Architecture
- SOLID principles
- Separation of concerns
- Repository Pattern
- Dependency Injection
- Lightweight Domain-Driven Design
- Provider Pattern
- API versioning
- Security by design
- Explainability first
- Human-in-the-loop AI

Core business logic must not depend directly on FastAPI, SQLAlchemy, ChromaDB, OpenAI, or other external frameworks.

---

# 6. High-Level Architecture

```text
React Frontend
        ↓
FastAPI REST API
        ↓
Application Services
        ↓
Domain Layer
        ↓
Analysis Orchestrator
        ↓
Validation and Secret Masking
        ↓
Parsing and Metadata Extraction
        ↓
Rules + Machine Learning Classification
        ↓
Evidence Extraction
        ↓
RAG Retrieval
        ↓
LLM Root-Cause Reasoning
        ↓
Recommendation and Guardrail Validation
        ↓
PostgreSQL + ChromaDB + File Storage
```

The Incident is the central business entity.

---

# 7. Core Domain Flow

```text
User
    ↓
Default Organization
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
Prediction
    ↓
Evidence
    ↓
Retrieved Documents
    ↓
Root-Cause Reasoning
    ↓
Recommendations
    ↓
Human Review
    ↓
Resolution
    ↓
Incident Report
```

---

# 8. Canonical User Workflow

The official MSc workflow is:

```text
Login
    ↓
Select or Create Project
    ↓
Create Draft Incident
    ↓
Upload Artifacts
    ↓
Validate and Mask Secrets
    ↓
Start Analysis
    ↓
Monitor Analysis Progress
    ↓
Review Classification
    ↓
Verify Evidence
    ↓
Review Retrieved Documentation
    ↓
Review Recommendations
    ↓
Add Human Notes
    ↓
Resolve Incident
    ↓
Generate Report
```

The upload wizard may create the draft incident automatically so the user does not experience unnecessary form complexity.

Files and analysis runs must always be associated with an incident.

---

# 9. Canonical Repository Structure

The official top-level structure is:

```text
devguard_ai/
├── backend/
├── frontend/
├── datasets/
├── knowledge_base/
├── infrastructure/
├── scripts/
├── tests/
├── docs/
├── .github/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

## 9.1 Backend AI Runtime Code

AI runtime implementation belongs inside:

```text
backend/app/ai/
```

Recommended subdirectories:

```text
backend/app/ai/
├── preprocessing/
├── parsers/
├── classification/
├── evidence/
├── retrieval/
├── reasoning/
├── recommendations/
├── guardrails/
├── providers/
└── evaluation/
```

## 9.2 Dataset Assets

Dataset artifacts belong inside:

```text
datasets/
├── raw/
├── sanitized/
├── labelled/
├── synthetic/
├── processed/
├── manifests/
├── schemas/
├── reports/
└── README.md
```

## 9.3 Knowledge Base Assets

```text
knowledge_base/
├── github_actions/
├── terraform/
├── aws/
├── processed/
├── manifests/
└── README.md
```

Do not create duplicate dataset or knowledge-base directories under multiple top-level locations.

---

# 10. Technology Stack

## Backend

- Python 3.11
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- Uvicorn

## Frontend

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Zustand
- React Hook Form
- Zod
- Tailwind CSS
- Recharts
- Lucide Icons
- Vitest
- React Testing Library
- Playwright

The frontend must not introduce Redux Toolkit or another styling framework unless an architecture decision approves the change.

## Data Storage

- PostgreSQL — primary relational database
- ChromaDB — MVP vector database
- Local file storage behind a storage interface for development
- Object-storage-compatible implementation for production evolution

## Machine Learning

- Scikit-learn
- TF-IDF
- Logistic Regression
- Optional comparison baselines such as Random Forest

## Embeddings

- Sentence Transformers

## LLM

- OpenAI through a provider interface

The architecture must remain provider-independent.

## Infrastructure

- Docker
- Docker Compose
- GitHub Actions
- Terraform
- AWS deployment target where required

---

# 11. Database Architecture

The database uses PostgreSQL with UUID primary keys and UTC timestamps.

## 11.1 Required MVP Tables

- users
- organizations
- organization_members
- projects
- pipeline_runs
- incidents
- uploaded_files
- analysis_runs
- failure_categories
- predictions
- evidence_items
- recommendations
- incident_events
- incident_resolutions
- incident_reports
- notifications
- model_versions
- evaluations
- feedback

## 11.2 Optional or Minimal MVP Tables

- project_integrations
- incident_assignments
- incident_notes
- knowledge_documents
- knowledge_chunks
- retrieved_documents
- audit_logs

These may be implemented fully or minimally depending on the active roadmap module, but the schema must preserve a clear migration path.

## 11.3 Database Rules

- Every important entity uses a UUID primary key.
- Every applicable entity uses `created_at` and `updated_at`.
- Tenant-owned entities use `organization_id`.
- Database access must go through repositories.
- Important operational records must not be permanently deleted.
- Use soft deletion or archival where appropriate.
- Secrets must never be stored in raw form.
- Important searchable values must not exist only inside JSONB.
- Multiple analysis runs may exist for one incident.
- One active classifier model is sufficient for the MVP.
- ChromaDB embeddings remain outside PostgreSQL.

---

# 12. API Architecture

## 12.1 API Version

```text
/api/v1
```

## 12.2 API Style

- RESTful JSON
- JWT Bearer authentication
- Thin route handlers
- Pydantic validation
- Application-service coordination
- Domain validation
- Repository persistence
- Standard error responses

## 12.3 Canonical Pagination Response

The official list-response format is:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total_items": 0,
  "total_pages": 0
}
```

Do not use a nested `pagination` object unless the API specification is formally revised.

## 12.4 Canonical Error Response

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource could not be found.",
    "details": null,
    "request_id": "req-..."
  }
}
```

## 12.5 Asynchronous Endpoints

The following operations should return `202 Accepted`:

- start analysis;
- reanalyse incident;
- regenerate recommendations;
- generate report;
- export large history datasets;
- webhook-triggered analysis in future versions.

The frontend initially polls status endpoints.

---

# 13. Authentication and Authorization

## 13.1 Authentication

Required capabilities:

- registration;
- login;
- access token;
- refresh token;
- token rotation;
- logout;
- current-user endpoint;
- password change;
- disabled-account protection.

## 13.2 Roles

The canonical role set is:

```text
platform_admin
organization_owner
organization_admin
engineer
viewer
```

For the MSc MVP, `organization_owner`, `engineer`, and `viewer` are the highest priority.

## 13.3 Authorization

Every protected operation must validate:

1. authentication;
2. role;
3. organization membership;
4. resource organization scope;
5. operation-specific permission.

Frontend visibility is not a security control. The backend must always enforce authorization.

---

# 14. File Upload and Security

## 14.1 Supported MVP Artifacts

- GitHub Actions logs
- GitHub Actions YAML
- Terraform `.tf`
- Terraform `.tfvars`
- Terraform output or plan text
- JSON metadata
- Plain-text diagnostic logs

ZIP support is deferred unless explicitly approved during the upload module.

## 14.2 Validation Pipeline

```text
Upload
    ↓
Extension Validation
    ↓
MIME and Content Detection
    ↓
Size Validation
    ↓
Encoding Validation
    ↓
Syntax Validation
    ↓
Secret Detection and Masking
    ↓
Normalization
    ↓
Metadata Extraction
    ↓
Ready for Analysis
```

## 14.3 Security Rules

- Reject executable content.
- Never trust file extensions or MIME type alone.
- Prevent path traversal.
- Generate safe storage names.
- Calculate checksums.
- Detect duplicate content.
- Do not execute uploaded code.
- Mask secrets before persistence, embeddings, retrieval, external AI calls, or report generation.
- Restrict file access by organization and project.
- Configure file-size limits through environment settings rather than hardcoding them.

---

# 15. AI Architecture

The AI pipeline is fixed:

```text
Input
    ↓
Validation
    ↓
Secret Masking
    ↓
Parsing and Normalization
    ↓
Metadata Extraction
    ↓
Rule-Based Signals
    ↓
TF-IDF Feature Extraction
    ↓
Machine Learning Classification
    ↓
Top-k Predictions
    ↓
Evidence Extraction
    ↓
Retrieval Query Construction
    ↓
ChromaDB Retrieval
    ↓
LLM Root-Cause Reasoning
    ↓
Recommendation Generation
    ↓
Confidence and Guardrail Validation
    ↓
Persistence
    ↓
Frontend
```

No component may bypass validation or secret masking.

The LLM must not reason directly from unrestricted raw uploads.

---

# 16. AI Design Principles

## 16.1 Explainability First

Every AI result must be traceable to:

- source file;
- line range;
- extracted error;
- retrieved documentation;
- model version;
- prompt version;
- dataset version;
- confidence score;
- analysis run.

## 16.2 Hybrid AI

The system combines:

- deterministic rules;
- traditional machine learning;
- evidence extraction;
- retrieval;
- large language models;
- guardrails;
- human feedback.

## 16.3 Deterministic Before Generative

Structured processing happens before LLM reasoning.

## 16.4 Provider Independence

External AI providers are accessed through interfaces.

## 16.5 Confidence-Aware Output

The system may return:

- high-confidence diagnosis;
- probable diagnosis;
- multiple possible causes;
- insufficient evidence.

Low-confidence results must be labelled clearly.

## 16.6 Human-in-the-Loop

Users may:

- confirm or reject a classification;
- rate recommendations;
- record the actual root cause;
- provide final resolution details;
- reopen an incident.

---

# 17. Analysis Execution Strategy

## 17.1 Initial MSc Implementation

Use:

```text
FastAPI BackgroundTasks
+ PostgreSQL analysis_run status
+ Frontend polling
```

This is acceptable for small-scale development and research experiments.

## 17.2 Production Evolution

Before production-scale deployment, the architecture may migrate to:

```text
Celery
+ Redis
+ Dedicated Worker Container
```

The application service must depend on an abstract task-execution interface so the background execution technology can be replaced without changing domain logic or API contracts.

## 17.3 Partial Result Policy

A useful partial result is preferable to complete failure.

Examples:

- classification may fall back to rules;
- evidence may be returned even if retrieval fails;
- template remediation may be returned if LLM reasoning fails;
- failed stages must be recorded safely;
- users must be informed that the output is partial.

---

# 18. Dataset Architecture

DevGuard AI uses a versioned multi-task dataset.

## 18.1 Primary Data Sources

- public GitHub Actions failures;
- public Terraform failures;
- public issue and pull-request discussions;
- controlled reproduced failures;
- safely collected official technical documentation.

## 18.2 Synthetic Data Policy

Synthetic data is supplementary only.

Rules:

- use synthetic samples only for severely underrepresented classes;
- label every synthetic sample explicitly;
- report the synthetic-data proportion;
- preserve generation metadata;
- do not place synthetic samples in the fixed test set;
- do not allow synthetic variants of the same source incident to cross dataset splits.

## 18.3 Dataset Splitting

Use group-aware train, validation, and test splits.

The fixed test set must remain stable for baseline comparison.

## 18.4 Required Dataset Controls

- source provenance;
- licensing or usage terms;
- secret redaction;
- duplicate detection;
- evidence-line validation;
- leakage checks;
- semantic versioning;
- dataset card;
- annotation guide;
- quality report.

---

# 19. RAG Architecture

The RAG knowledge base must be separate from the failure dataset.

Preferred sources:

- official GitHub documentation;
- official Terraform documentation;
- official AWS documentation;
- approved internal guidance in future versions.

Each knowledge document must record:

- source;
- title;
- provider;
- product;
- version or collection date;
- status;
- licensing or usage terms.

The system must store retrieved document references for every grounded analysis.

---

# 20. Frontend Architecture

## 20.1 Frontend Principles

- reusable components;
- dark mode by default;
- responsive;
- accessible;
- enterprise appearance;
- consistent loading, empty, error, and success states;
- no duplicated UI logic;
- no raw exceptions;
- role-aware navigation;
- clear confidence and evidence presentation.

## 20.2 Required MSc Screens

- Login
- Dashboard
- Projects
- Project Details
- Create Incident / Upload Wizard
- Analysis Progress
- Incident Details
- Evidence Viewer
- Recommendations
- Timeline
- Notes
- Resolution
- Reports
- History
- Evaluation
- Notifications
- Profile

## 20.3 Commercial or Stretch Screens

- advanced organization management;
- model activation controls;
- complete audit administration;
- global enterprise search;
- billing;
- advanced team management;
- complex executive analytics.

Architecture and routes may preserve future extension points, but these features must not block delivery of the MSc MVP.

---

# 21. Design System

The approved primary design system is:

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

Layout:

```text
Sidebar: 240px
Top Bar: 72px
Spacing System: 8px
Card Radius: 14px
Button Height: 44px
Button Radius: 12px
```

When older screen documents contain different visual values, this section takes precedence.

---

# 22. Testing Architecture

Every module requires:

- unit tests;
- integration tests;
- manual verification;
- documentation.

Critical workflows require end-to-end tests.

## 22.1 Testing Pyramid

Recommended distribution:

```text
Unit Tests:        approximately 70%
Integration Tests: approximately 25%
End-to-End Tests:  approximately 5%
```

## 22.2 Mandatory Quality Commands

Backend:

```bash
ruff check .
ruff format --check .
mypy app
pytest
alembic upgrade head
```

Frontend:

```bash
npm run lint
npm run typecheck
npm run test
npm run build
```

End-to-end:

```bash
npx playwright test
```

## 22.3 Required Security Tests

- invalid and expired tokens;
- disabled accounts;
- permission denial;
- cross-organization access;
- unsafe uploads;
- path traversal;
- secret exposure;
- SQL injection resistance;
- XSS and unsafe Markdown;
- report authorization;
- prompt injection handling.

---

# 23. Observability

## Logging

- structured logs;
- request IDs;
- correlation IDs;
- safe error details;
- no passwords, tokens, secrets, or unredacted logs.

## Metrics

- API latency;
- error rate;
- analysis latency;
- analysis failure rate;
- model inference latency;
- retrieval latency;
- LLM latency and cost;
- database health;
- queue or task backlog when workers are introduced.

## Audit Events

Priority events:

- registration;
- successful and failed login;
- password change;
- role change;
- user disable or enable;
- project creation;
- incident creation;
- file upload;
- analysis start and completion;
- incident resolution;
- report generation.

---

# 24. Deployment Architecture

## Environments

- development;
- test;
- staging;
- production.

## CI/CD Flow

```text
Pull Request or Main Branch Update
        ↓
Lint
        ↓
Type Check
        ↓
Unit Tests
        ↓
Integration Tests
        ↓
Frontend Build
        ↓
Docker Build
        ↓
Security Scan
        ↓
Push Container Images
        ↓
Deploy
        ↓
Database Migration
        ↓
Smoke Tests
```

Production Docker images should use multi-stage builds.

Rollback procedures and database migration recovery must be documented before production deployment.

---

# 25. Canonical Implementation Phases

The official phase numbering is:

```text
Phase 1  — Foundation
Phase 2  — Core Platform
Phase 3  — Business Domain
Phase 4  — Dataset Pipeline
Phase 5  — Machine Learning
Phase 6  — AI Intelligence
Phase 7  — Enterprise Frontend
Phase 8  — Application Integration
Phase 9  — End-to-End Validation
Phase 10 — Research Evaluation
Phase 11 — Deployment
Phase 12 — Observability
Phase 13 — Security Hardening
Phase 14 — Commercial Expansion
```

Roadmap documents that use overlapping phase numbers must be interpreted according to this canonical sequence.

---

# 26. Canonical Module Order

Implementation must proceed in this order:

```text
Module 1  — Foundation
Module 2  — Database Foundation
Module 3  — Authentication and Authorization
Module 4  — Project and Incident Domain
Module 5  — File Upload and Validation
Module 6  — Dataset Pipeline
Module 7  — Machine Learning
Module 8  — Evidence Extraction
Module 9  — Knowledge Base and RAG
Module 10 — LLM Reasoning and Recommendations
Module 11 — Analysis Orchestration
Module 12 — Frontend
Module 13 — Integration
Module 14 — Evaluation
Module 15 — Deployment and Hardening
```

Small frontend foundations may be created early, but complete frontend feature implementation must not bypass backend domain and API readiness.

---

# 27. Development Workflow

Every module follows:

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

Do not begin the next module while unresolved critical defects remain.

---

# 28. Definition of Architecture Freeze

The following are frozen for Version 1.0:

- modular-monolith style;
- canonical repository structure;
- technology stack;
- PostgreSQL database;
- ChromaDB vector store;
- REST API version;
- incident-centred domain;
- organization-ready MVP model;
- canonical pagination format;
- AI pipeline order;
- validation and secret-masking requirements;
- dataset schema and synthetic-data policy;
- frontend design system;
- implementation phase numbering;
- module order.

A change requires:

1. a written architecture-decision record;
2. explanation of the problem;
3. proposed alternatives;
4. impact assessment;
5. explicit approval before implementation.

---

# 29. Architecture Decision Log Required Before Coding

Create:

```text
docs/ARCHITECTURE_DECISION_LOG.md
```

At minimum, record these approved decisions:

- ADR-001: Modular monolith for the MSc MVP
- ADR-002: Minimal default-organization model
- ADR-003: Canonical root-level project structure
- ADR-004: Root-level API pagination fields
- ADR-005: Draft incident created before file upload
- ADR-006: FastAPI BackgroundTasks initially, worker abstraction retained
- ADR-007: Public and reproduced data first; synthetic data supplementary
- ADR-008: Canonical phase numbering
- ADR-009: Zustand selected for frontend client state
- ADR-010: Tailwind CSS selected as the frontend styling system
- ADR-011: ZIP upload deferred unless separately approved

---

# 30. Research Mapping

## RQ1 — Failure Classification

Implemented by:

- preprocessing;
- rules;
- TF-IDF;
- machine learning classifier;
- top-k prediction.

## RQ2 — Evidence Extraction

Implemented by:

- deterministic patterns;
- parsed error structures;
- line-span extraction;
- evidence-ranking logic.

## RQ3 — Root-Cause Analysis and Recommendations

Implemented by:

- retrieval query builder;
- ChromaDB;
- prompt builder;
- LLM provider;
- recommendation engine;
- confidence and guardrails.

## RQ4 — Evaluation

Implemented by:

- rules-only baseline;
- ML-only baseline;
- LLM without RAG;
- LLM with RAG;
- full DevGuard AI method;
- quantitative metrics;
- qualitative usefulness evaluation.

---

# 31. Evaluation Metrics

## Classification

- accuracy;
- precision;
- recall;
- F1 score;
- top-k accuracy;
- confusion matrix.

## Evidence

- evidence precision;
- evidence recall;
- line-span overlap where appropriate.

## Retrieval

- retrieval precision;
- context relevance;
- source usefulness.

## Reasoning and Recommendations

- correctness;
- grounding;
- explainability;
- actionability;
- safety;
- prevention quality;
- hallucination rate.

## Operational

- end-to-end latency;
- cost per analysis;
- analysis success rate;
- mean time to resolution;
- recommendation acceptance;
- user usefulness rating.

---

# 32. Current Project Status

Architecture:

```text
Complete and frozen in Version 1.1
```

Documentation:

```text
Sufficient to begin implementation
```

Implementation:

```text
Ready to begin with repository cleanup, ADR creation, and foundation verification
```

Dataset:

```text
Not started
```

Machine Learning:

```text
Not started
```

Backend:

```text
Foundation may already exist and must be verified against this document
```

Frontend:

```text
Foundation may already exist and must be verified against this document
```

Deployment:

```text
Development Docker environment may exist; production deployment not started
```

---

# 33. Rules for Cursor and Other Coding Assistants

Before implementing a module, the coding assistant must read:

1. `MASTER_ARCHITECTURE.md`
2. `PROJECT_CONSTITUTION.md`
3. `ARCHITECTURE_DECISION_LOG.md`
4. the relevant roadmap section;
5. the relevant specialized architecture document.

The coding assistant must not:

- change the architecture;
- introduce unapproved technologies;
- create duplicate folders;
- modify the schema outside approved migrations;
- invent API contracts;
- change enum values independently;
- skip module order;
- remove tests;
- bypass validation;
- send unredacted data to an external model;
- implement commercial scope before required MSc features;
- generate the complete project in one operation.

When a change appears necessary, the assistant must explain the reason and wait for approval.

---

# 34. Definition of Success

The MSc implementation is successful when:

- users can register and authenticate securely;
- a default organization and membership are created safely;
- users can create projects;
- users can create incidents;
- users can upload GitHub Actions, YAML, and Terraform artifacts;
- files are validated and secrets are masked;
- the system classifies failures;
- evidence is extracted with source references;
- relevant official documentation is retrieved;
- the LLM generates grounded root-cause reasoning;
- recommendations are structured and confidence-aware;
- users can review, resolve, and reopen incidents;
- reports are generated;
- history and evaluation metrics are available;
- end-to-end tests pass;
- research experiments are reproducible;
- the architecture can evolve into a commercial SaaS platform without major redesign.

---

# 35. Approved Starting Point

Implementation begins with:

```text
1. Normalize filenames and documentation paths.
2. Create ARCHITECTURE_DECISION_LOG.md.
3. Verify the canonical repository structure.
4. Verify backend and frontend startup.
5. Verify Docker Compose and PostgreSQL connectivity.
6. Verify environment validation and structured logging.
7. Inspect existing migrations and models.
8. Begin the next incomplete module according to the canonical module order.
```

No dataset, ML, RAG, LLM, or advanced frontend work should begin before the foundation and database architecture pass their quality gates.

---

# 36. Final Principle

DevGuard AI is not just an academic prototype.

Every design decision must answer:

> Can this implementation satisfy the MSc research objectives now and grow into a production-grade SaaS platform later without major redesign?

If the answer is no, record an architecture decision and correct the design before implementation.

---

**End of MASTER_ARCHITECTURE.md — Version 1.1**
