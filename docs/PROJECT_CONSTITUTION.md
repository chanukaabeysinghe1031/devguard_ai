# DevGuard AI — Project Constitution

**Version:** 1.1  
**Status:** APPROVED AND FROZEN FOR IMPLEMENTATION  
**Last Updated:** July 2026  
**Project Type:** MSc Advanced Software Engineering Dissertation + Commercial SaaS Foundation

---

# 1. Purpose

This constitution defines the mandatory rules for designing, implementing, testing, documenting, and evolving DevGuard AI.

It applies to:

- the project owner;
- developers;
- reviewers;
- Cursor;
- AI coding assistants;
- automation tools;
- future contributors.

This document is subordinate only to `MASTER_ARCHITECTURE.md`.

When conflicts exist, the authority order is:

1. `MASTER_ARCHITECTURE.md`
2. `PROJECT_CONSTITUTION.md`
3. `PROJECT_STRUCTURE.md`
4. Specialized architecture documents
5. Implementation roadmap
6. Screen specifications
7. UI prompt collection

No contributor may override this order.

---

# 2. Project Vision

DevGuard AI is an AI-powered DevOps Incident Intelligence Platform.

It analyses CI/CD failures, Infrastructure-as-Code artifacts, deployment configurations, and related evidence to:

- classify failures;
- identify the failed stage and component;
- extract supporting evidence;
- retrieve relevant technical knowledge;
- generate grounded root-cause explanations;
- generate remediation and prevention recommendations;
- support incident resolution;
- produce research evaluation results.

The project has two equally important goals:

1. Complete the MSc dissertation successfully.
2. Build a maintainable foundation for a future commercial SaaS platform.

Every technical decision must support the MSc scope without blocking future commercial evolution.

---

# 3. Core Principles

Every module must follow these principles:

- Clean Architecture
- SOLID principles
- Separation of concerns
- High maintainability
- Extensibility
- Testability
- Security first
- Explainability first
- Reusability
- Provider independence
- Human-in-the-loop AI
- Production-quality engineering
- Minimal accidental complexity

The system must remain understandable by a single developer while being extensible enough for future team development.

---

# 4. Architectural Discipline

## 4.1 Architecture Is Frozen

The following are frozen for Version 1.0:

- modular monolith architecture;
- canonical project structure;
- incident-centred domain model;
- PostgreSQL database;
- ChromaDB vector store;
- FastAPI backend;
- React and TypeScript frontend;
- REST API version `/api/v1`;
- canonical pagination response;
- organization-ready MVP model;
- AI pipeline order;
- dataset policy;
- phase numbering;
- module order;
- security and secret-redaction requirements.

No contributor may change these items without an approved architecture decision record.

## 4.2 No Silent Architecture Changes

A proposed change must include:

1. the problem;
2. why the current design is insufficient;
3. alternatives considered;
4. impact on database, API, AI, frontend, testing, and deployment;
5. migration requirements;
6. explicit approval.

The change must be recorded in:

```text
docs/ARCHITECTURE_DECISION_LOG.md
```

---

# 5. Development Philosophy

DevGuard AI is not a disposable university prototype.

It must be implemented as software that can be:

- tested;
- reviewed;
- deployed;
- monitored;
- maintained;
- extended;
- evaluated scientifically.

Speed is important, but speed must not be achieved by breaking architecture, removing tests, hardcoding configuration, or bypassing security.

---

# 6. Golden Rules

## Rule 1 — Build Module by Module

Never generate or implement the entire platform at once.

Each module must be completed before the next dependent module begins.

## Rule 2 — Explain Before Coding

Before writing code, explain:

- what will be built;
- why it is needed;
- dependencies;
- affected files;
- database impact;
- API impact;
- tests required.

## Rule 3 — Keep the System Working

Every module must compile, start, and pass its required checks before moving forward.

## Rule 4 — Every Module Requires Tests

At minimum:

- unit tests;
- integration tests where infrastructure is involved;
- manual verification notes.

Critical workflows require end-to-end tests.

## Rule 5 — Every Module Requires Documentation

No undocumented module is complete.

## Rule 6 — Never Duplicate Business Logic

Business rules belong in domain or application services, not repeated across routes, repositories, background tasks, and frontend code.

## Rule 7 — Never Hardcode Configuration

Use environment configuration for:

- database URLs;
- JWT settings;
- file limits;
- storage locations;
- AI provider settings;
- model paths;
- vector database settings;
- logging levels;
- CORS;
- retention settings.

## Rule 8 — Never Expose Secrets

Never log, persist, return, embed, or send raw secrets to external AI providers.

## Rule 9 — Preserve Traceability

Every AI result must be traceable to:

- analysis run;
- source file;
- line range;
- model version;
- prompt version;
- dataset version;
- retrieved documents;
- confidence score.

## Rule 10 — Human Confirmation Is Required

The system may recommend actions but must not automatically:

- modify Terraform;
- modify IAM policies;
- execute shell commands;
- rerun production deployments;
- apply Kubernetes changes;
- close incidents;
- approve pull requests.

## Rule 11 — Keep Scope Controlled

The MSc MVP must not be delayed by commercial features.

## Rule 12 — Prefer Simple Production-Ready Solutions

Choose the simplest solution that preserves correctness, security, testing, and future extensibility.

---

# 7. Canonical Implementation Order

Implementation must follow this order:

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

Small frontend shell work may begin early, but feature implementation must not bypass backend readiness.

The order may change only through an approved ADR.

---

# 8. Module Lifecycle

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

# 9. Repository Rules

## 9.1 Canonical Top-Level Structure

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

Do not create duplicate directories such as:

```text
ai/datasets/
backend/datasets/
docs/docs/
knowledge_base/knowledge_base/
```

AI runtime code belongs under:

```text
backend/app/ai/
```

Research data belongs under:

```text
datasets/
```

Knowledge documents belong under:

```text
knowledge_base/
```

## 9.2 File Naming

- Use clear lowercase snake_case for Python files.
- Use consistent TypeScript naming.
- Remove duplicate suffixes such as `(1)` from official documentation.
- Do not create multiple “final”, “new”, or “updated” copies inside the repository.
- Replace obsolete documents through version control.

---

# 10. Git Rules

Use small, reviewable commits.

Recommended commit prefixes:

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

Branches:

```text
main
develop
feature/*
fix/*
refactor/*
docs/*
release/*
```

Never commit:

- `.env`;
- API keys;
- passwords;
- access tokens;
- refresh tokens;
- private keys;
- raw secrets;
- large raw datasets;
- trained model artifacts unless explicitly approved;
- local database files;
- generated caches;
- unredacted logs.

Every pull request should describe:

- purpose;
- affected modules;
- tests;
- database changes;
- API changes;
- security impact;
- documentation changes.

---

# 11. Backend Coding Standards

Every Python file must follow:

- PEP 8;
- type hints;
- meaningful names;
- small reusable functions;
- Single Responsibility Principle;
- no magic numbers;
- no duplicated logic;
- proper logging;
- proper exception handling;
- dependency injection;
- framework-independent domain logic.

Required checks:

```bash
ruff check .
ruff format --check .
mypy app
pytest
```

Route handlers must remain thin.

Preferred flow:

```text
FastAPI Route
    ↓
Application Service
    ↓
Domain Rule
    ↓
Repository or Provider
    ↓
Database / AI / Storage
```

Routes must not contain business logic or direct persistence logic.

---

# 12. Frontend Coding Standards

The canonical frontend stack is:

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

Do not introduce Redux Toolkit, CSS Modules, styled-components, or another primary UI framework without approval.

Frontend rules:

- use reusable components;
- avoid duplicated UI logic;
- use TanStack Query for server state;
- keep global client state minimal;
- centralize API communication;
- use shared validation schemas;
- handle loading, empty, success, and error states;
- never expose raw stack traces;
- clear sensitive state on logout;
- enforce permission visibility, while relying on backend authorization;
- support keyboard navigation;
- maintain accessible focus states;
- do not communicate status only through colour.

Required checks:

```bash
npm run lint
npm run typecheck
npm run test
npm run build
npx playwright test
```

---

# 13. Database Rules

- Use PostgreSQL.
- Use SQLAlchemy.
- Use Alembic for every schema change.
- Use UUID primary keys.
- Use timezone-aware timestamps.
- Use repositories for database access.
- Use transactions consistently.
- Prefer archive or soft deletion for important records.
- Keep tenant-owned records organization-scoped.
- Do not store raw secrets.
- Do not store passwords; store secure password hashes only.
- Do not rename tables or fields outside approved migrations.
- Do not rely on JSONB for values that require filtering, indexing, or constraints.
- Preserve historical analysis runs.
- Preserve resolution history.
- Never edit production schema manually.

Every migration must:

- upgrade cleanly;
- downgrade where reasonably possible;
- run against an empty database;
- preserve existing data where applicable;
- include tests or verification steps.

---

# 14. API Standards

All APIs use:

```text
/api/v1
```

Protected APIs require JWT Bearer authentication.

## 14.1 Canonical Pagination

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total_items": 0,
  "total_pages": 0
}
```

Do not use a nested pagination object unless the API specification is formally revised.

## 14.2 Canonical Error Format

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

## 14.3 API Behaviour

- Return consistent status codes.
- Return `202 Accepted` for asynchronous operations.
- Validate input through Pydantic.
- Prevent mass assignment.
- Do not expose password hashes.
- Do not expose raw secrets.
- Do not expose internal storage paths.
- Include request IDs in errors.
- Keep OpenAPI documentation accurate.
- Never invent endpoints outside the approved API specification.

---

# 15. Authentication Rules

Required:

- registration;
- login;
- access tokens;
- refresh tokens;
- token rotation;
- logout;
- current-user endpoint;
- password change;
- disabled-account protection.

Security rules:

- normalize emails;
- use secure password hashing;
- use short-lived access tokens;
- distinguish access and refresh token types;
- define refresh-token revocation;
- never log tokens;
- rate-limit authentication endpoints;
- reject expired and malformed tokens;
- clear frontend authentication state on logout.

---

# 16. Authorization Rules

Canonical roles:

```text
platform_admin
organization_owner
organization_admin
engineer
viewer
```

For every protected resource, validate:

1. authenticated user;
2. role;
3. organization membership;
4. resource organization;
5. operation permission.

Cross-organization access must be blocked.

Frontend role restrictions are not sufficient. The backend must enforce all permissions.

---

# 17. Organization Scope Rules

The MSc MVP uses a minimal organization-ready model.

Required:

- create one default organization;
- create an owner membership;
- include organization scope on tenant-owned records;
- enforce organization filtering;
- test cross-organization access.

Deferred:

- organization switching;
- invitations;
- multiple organizations per user;
- billing;
- subscription plans;
- enterprise SSO;
- advanced team administration.

Do not expand into full commercial multi-tenancy during the MSc MVP unless explicitly approved.

---

# 18. Incident Workflow Rules

The Incident is the central business entity.

Canonical workflow:

```text
Project
    ↓
Pipeline Run
    ↓
Draft Incident
    ↓
Uploaded Files
    ↓
Validation
    ↓
Analysis Run
    ↓
Prediction and Evidence
    ↓
Recommendations
    ↓
Human Review
    ↓
Resolution
    ↓
Report
```

Files and analysis runs must always be associated with an incident.

The upload wizard may create the draft incident automatically.

Do not create analysis results that cannot be traced to an incident and analysis run.

---

# 19. File Upload Rules

Supported MVP files:

- GitHub Actions logs;
- GitHub Actions YAML;
- Terraform `.tf`;
- Terraform `.tfvars`;
- Terraform text output;
- JSON metadata;
- plain-text diagnostic logs.

ZIP upload is deferred unless approved.

Every upload must validate:

- extension;
- MIME type;
- content type;
- file size;
- encoding;
- syntax where practical;
- checksum;
- duplicate status;
- path safety;
- secret patterns.

Never:

- execute uploaded content;
- trust filenames;
- trust extensions alone;
- expose filesystem paths;
- send raw uploaded files to an external LLM;
- store exposed secrets.

---

# 20. Security Rules

Security is mandatory at every layer.

Always:

- validate uploaded files;
- mask secrets before persistence;
- mask secrets before embeddings;
- mask secrets before RAG;
- mask secrets before LLM submission;
- mask secrets before reports;
- use parameterized database access;
- sanitize Markdown and user-generated content;
- restrict file and report access;
- verify organization scope;
- log privileged actions;
- use secure headers;
- protect CORS configuration;
- use environment-based secrets;
- scan dependencies and containers;
- prevent path traversal;
- defend against prompt injection.

Never expose:

- AWS keys;
- GitHub tokens;
- passwords;
- access tokens;
- refresh tokens;
- private keys;
- database credentials;
- internal stack traces.

---

# 21. AI Pipeline Rules

The canonical AI pipeline is:

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
Rules
    ↓
TF-IDF
    ↓
Machine Learning Classification
    ↓
Top-k Predictions
    ↓
Evidence Extraction
    ↓
RAG Retrieval
    ↓
LLM Reasoning
    ↓
Recommendation Generation
    ↓
Confidence and Guardrails
    ↓
Persistence
```

No stage may bypass validation or secret masking.

The LLM must not receive unrestricted raw input.

---

# 22. Machine Learning Rules

- Version every model.
- Record dataset version.
- Record training configuration.
- Save evaluation metrics.
- Never overwrite model artifacts silently.
- Preserve the fixed test set.
- Store every prediction with:
  - predicted class;
  - confidence;
  - rank;
  - model version;
  - timestamp;
  - analysis run.
- Include an `unknown` or insufficient-evidence path where appropriate.
- Compare against required baselines.
- Ensure reproducibility through fixed seeds and recorded configuration.

---

# 23. Dataset Rules

Primary sources:

- public failures;
- controlled reproduced failures;
- approved official documentation.

Synthetic data is supplementary only.

Synthetic data rules:

- use only for underrepresented categories;
- label clearly;
- record generation metadata;
- report synthetic proportion;
- keep synthetic data out of the fixed test set;
- prevent source-related leakage across splits.

Every sample must record:

- unique ID;
- provenance;
- source type;
- licensing or usage terms;
- checksum;
- category;
- split;
- redaction status;
- evidence spans where applicable.

Required validation:

- schema validity;
- duplicate detection;
- label validity;
- line-range validity;
- secret checks;
- leakage checks;
- class distribution;
- split distribution;
- source provenance.

---

# 24. RAG Rules

The knowledge base must remain separate from the failure dataset.

Prefer official documentation.

Every document must record:

- source URL or source identifier;
- title;
- provider;
- product;
- version or collection date;
- status;
- licensing or terms.

The system must:

- retrieve before grounded LLM reasoning;
- store retrieved references;
- preserve ranking and similarity metadata;
- distinguish official and community sources;
- mark outdated documents;
- avoid duplicate chunks.

The system may return partial results if retrieval fails, but the output must clearly state that RAG context was unavailable.

---

# 25. LLM and Prompt Rules

LLM prompts must:

- use structured system instructions;
- include the predicted category;
- include sanitized evidence;
- include retrieved context;
- delimit untrusted log content;
- request structured JSON output;
- include uncertainty instructions;
- prohibit command execution;
- require evidence-based reasoning.

LLM output must:

- pass schema validation;
- be treated as untrusted until validated;
- include uncertainty;
- avoid unsupported claims;
- avoid exposing secrets;
- never trigger tools or execute actions directly.

Prompt versions must be recorded.

---

# 26. Confidence and Guardrail Rules

Confidence must consider:

- ML probability;
- rule agreement;
- evidence quality;
- retrieval relevance;
- output consistency.

The UI must clearly distinguish:

- high confidence;
- probable diagnosis;
- multiple possible causes;
- insufficient evidence;
- partial result.

Low confidence must never be presented as proven fact.

---

# 27. Background Processing Rules

Initial MSc strategy:

```text
FastAPI BackgroundTasks
+ PostgreSQL analysis_run status
+ Frontend polling
```

The code must depend on an execution abstraction so the system can later move to:

```text
Celery
+ Redis
+ Worker Container
```

Background tasks must:

- record status;
- record timestamps;
- record safe failure reasons;
- avoid duplicate active runs;
- support retry where defined;
- preserve partial results;
- not hide failures.

---

# 28. Error Handling Rules

Never ignore exceptions.

Always:

- catch at the appropriate boundary;
- log safely;
- map infrastructure errors to domain or application errors;
- return meaningful API errors;
- include request IDs;
- preserve internal diagnostic detail in logs only;
- avoid exposing stack traces.

Partial AI results are allowed when useful and safe.

A failure in one optional AI stage must not destroy already valid outputs.

---

# 29. Logging Rules

Use structured logging.

Never use `print()` for application logging.

Every error log should include where applicable:

- timestamp;
- level;
- module;
- function;
- request ID;
- correlation ID;
- organization ID;
- incident ID;
- analysis run ID;
- safe error details.

Never log:

- passwords;
- JWTs;
- API keys;
- private keys;
- raw secrets;
- unredacted logs;
- sensitive report contents.

---

# 30. Testing Rules

Every module requires:

- unit tests;
- integration tests;
- manual verification;
- documentation.

Critical workflows require end-to-end tests.

Required security tests include:

- authentication bypass;
- expired tokens;
- disabled users;
- role denial;
- cross-organization access;
- unsafe uploads;
- path traversal;
- SQL injection resistance;
- XSS;
- unsafe Markdown;
- secret leakage;
- prompt injection;
- report authorization.

Tests must be deterministic where possible.

A module is not complete while tests are skipped without justification.

---

# 31. Documentation Rules

Every module requires:

- purpose;
- architecture notes;
- setup instructions;
- configuration;
- API changes;
- database changes;
- usage examples;
- test instructions;
- known limitations.

No undocumented module is complete.

Documentation filenames must be stable and canonical.

Do not maintain multiple competing versions of the same official document in the repository.

---

# 32. Scope Control

## Required MSc Scope

- authentication;
- default organization;
- projects;
- incidents;
- manual upload;
- file validation;
- GitHub Actions;
- Terraform;
- failure classification;
- evidence extraction;
- RAG;
- LLM reasoning;
- recommendations;
- confidence;
- resolution;
- reports;
- history;
- evaluation;
- basic frontend;
- Docker-based development;
- CI/CD;
- security testing.

## Deferred Commercial Scope

- billing;
- subscriptions;
- multi-organization switching;
- invitations;
- SSO;
- Slack and Teams;
- GitLab;
- Jenkins;
- Azure DevOps;
- Kubernetes;
- automated remediation;
- self-healing;
- predictive deployment risk;
- plugin marketplace;
- advanced enterprise administration.

Deferred features must not block required MSc delivery.

---

# 33. Definition of Done

A module is complete only when:

- architecture was reviewed;
- code is implemented;
- code compiles;
- type checks pass;
- linting passes;
- unit tests pass;
- required integration tests pass;
- security requirements are satisfied;
- API contracts are updated;
- database migrations work where applicable;
- frontend states work where applicable;
- documentation is complete;
- no critical TODO remains;
- no known critical defect remains;
- the module is reviewed and approved.

---

# 34. Rules for Cursor and AI Coding Assistants

Before coding, read:

1. `MASTER_ARCHITECTURE.md`
2. `PROJECT_CONSTITUTION.md`
3. `ARCHITECTURE_DECISION_LOG.md`
4. relevant roadmap section
5. relevant architecture specification

The coding assistant must not:

- alter architecture;
- add unapproved technologies;
- change canonical folders;
- invent APIs;
- change enum values independently;
- alter schema without migration approval;
- bypass repositories;
- put business logic in routes;
- skip tests;
- skip documentation;
- send unredacted data to an LLM;
- implement commercial scope before MSc requirements;
- generate the entire project at once;
- mark work complete when checks fail.

When uncertainty exists, stop and explain the issue before implementation.

---

# 35. Initial Approved Actions

Implementation may begin with:

```text
1. Normalize documentation filenames.
2. Create ARCHITECTURE_DECISION_LOG.md.
3. Verify repository structure.
4. Verify backend startup.
5. Verify frontend startup.
6. Verify Docker Compose.
7. Verify PostgreSQL connectivity.
8. Verify environment validation.
9. Verify structured logging.
10. Inspect existing migrations and models.
11. Continue from the first incomplete canonical module.
```

Do not begin advanced AI or frontend feature work before foundation and database quality gates pass.

---

# 36. Final Principle

Every decision must answer:

> Does this implementation satisfy the MSc research objectives now while preserving a safe path to a production-grade SaaS platform later?

If the answer is no, stop, document the issue, and obtain architectural approval before proceeding.

---

**End of PROJECT_CONSTITUTION.md — Version 1.1**
