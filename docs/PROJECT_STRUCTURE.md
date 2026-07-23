# DevGuard AI – Project Structure

**Version:** 1.0  
**Status:** Proposed  
**Purpose:** Define the directory structure and responsibility boundaries for the DevGuard AI MSc MVP and future commercial SaaS evolution.

---

## 1. Repository Structure

```text
devguard_ai/
├── backend/
├── frontend/
├── docs/
├── datasets/
├── knowledge_base/
├── infrastructure/
├── scripts/
├── tests/
├── .github/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

---

## 2. Backend Structure

```text
backend/
├── app/
│   ├── api/
│   │   ├── dependencies/
│   │   ├── error_handlers/
│   │   └── v1/
│   │       ├── routes/
│   │       │   ├── auth.py
│   │       │   ├── users.py
│   │       │   ├── projects.py
│   │       │   ├── uploads.py
│   │       │   ├── pipeline_runs.py
│   │       │   ├── incidents.py
│   │       │   ├── analyses.py
│   │       │   ├── notifications.py
│   │       │   ├── reports.py
│   │       │   ├── history.py
│   │       │   └── health.py
│   │       └── router.py
│   │
│   ├── application/
│   │   ├── dto/
│   │   ├── commands/
│   │   ├── queries/
│   │   ├── mappers/
│   │   └── services/
│   │       ├── authentication_service.py
│   │       ├── project_service.py
│   │       ├── upload_service.py
│   │       ├── pipeline_run_service.py
│   │       ├── incident_service.py
│   │       ├── analysis_service.py
│   │       ├── notification_service.py
│   │       ├── report_service.py
│   │       └── history_service.py
│   │
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── uploaded_file.py
│   │   │   ├── pipeline_run.py
│   │   │   ├── incident.py
│   │   │   ├── prediction.py
│   │   │   ├── evidence_item.py
│   │   │   ├── recommendation.py
│   │   │   ├── notification.py
│   │   │   ├── incident_note.py
│   │   │   ├── incident_report.py
│   │   │   ├── evaluation.py
│   │   │   └── feedback.py
│   │   ├── enums/
│   │   │   ├── user_role.py
│   │   │   ├── file_type.py
│   │   │   ├── pipeline_status.py
│   │   │   ├── incident_status.py
│   │   │   ├── incident_severity.py
│   │   │   ├── notification_type.py
│   │   │   ├── evidence_type.py
│   │   │   └── risk_level.py
│   │   ├── exceptions/
│   │   ├── interfaces/
│   │   │   ├── repositories.py
│   │   │   ├── ai_services.py
│   │   │   ├── notification_providers.py
│   │   │   ├── storage_provider.py
│   │   │   └── report_generator.py
│   │   └── value_objects/
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   │   ├── models/
│   │   │   ├── repositories/
│   │   │   ├── migrations/
│   │   │   ├── session.py
│   │   │   ├── base.py
│   │   │   └── seed.py
│   │   ├── storage/
│   │   │   ├── local_storage.py
│   │   │   └── object_storage.py
│   │   ├── notifications/
│   │   │   ├── in_app_provider.py
│   │   │   ├── email_provider.py
│   │   │   ├── slack_provider.py
│   │   │   └── teams_provider.py
│   │   ├── reports/
│   │   │   ├── pdf_generator.py
│   │   │   ├── markdown_generator.py
│   │   │   └── json_generator.py
│   │   ├── providers/
│   │   │   ├── cicd/
│   │   │   │   ├── github_actions_provider.py
│   │   │   │   ├── gitlab_provider.py
│   │   │   │   ├── jenkins_provider.py
│   │   │   │   └── azure_devops_provider.py
│   │   │   ├── cloud/
│   │   │   │   ├── aws_provider.py
│   │   │   │   ├── azure_provider.py
│   │   │   │   └── gcp_provider.py
│   │   │   └── iac/
│   │   │       ├── terraform_provider.py
│   │   │       ├── docker_provider.py
│   │   │       ├── kubernetes_provider.py
│   │   │       └── pulumi_provider.py
│   │   └── external/
│   │       ├── openai_client.py
│   │       └── github_client.py
│   │
│   ├── ai/
│   │   ├── orchestration/
│   │   │   ├── analysis_orchestrator.py
│   │   │   └── analysis_context.py
│   │   ├── preprocessing/
│   │   │   ├── log_cleaner.py
│   │   │   ├── secret_masker.py
│   │   │   ├── metadata_extractor.py
│   │   │   └── file_normalizer.py
│   │   ├── classification/
│   │   │   ├── feature_extractor.py
│   │   │   ├── classifier.py
│   │   │   ├── confidence_calculator.py
│   │   │   └── model_loader.py
│   │   ├── evidence/
│   │   │   ├── log_evidence_extractor.py
│   │   │   ├── stack_trace_extractor.py
│   │   │   ├── terraform_evidence_extractor.py
│   │   │   └── evidence_ranker.py
│   │   ├── rag/
│   │   │   ├── document_loader.py
│   │   │   ├── chunker.py
│   │   │   ├── embedding_service.py
│   │   │   ├── vector_store.py
│   │   │   └── retriever.py
│   │   ├── reasoning/
│   │   │   ├── prompt_builder.py
│   │   │   ├── llm_service.py
│   │   │   ├── root_cause_analyzer.py
│   │   │   └── recommendation_generator.py
│   │   ├── evaluation/
│   │   │   ├── classification_metrics.py
│   │   │   ├── evidence_metrics.py
│   │   │   ├── recommendation_metrics.py
│   │   │   └── experiment_runner.py
│   │   └── models/
│   │       ├── trained/
│   │       ├── vectorizers/
│   │       └── metadata/
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── middleware.py
│   │   ├── security.py
│   │   ├── constants.py
│   │   └── dependencies.py
│   │
│   ├── utils/
│   │   ├── datetime.py
│   │   ├── identifiers.py
│   │   ├── pagination.py
│   │   ├── file_utils.py
│   │   └── validation.py
│   │
│   └── main.py
│
├── alembic/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── api/
│   ├── ai/
│   ├── repositories/
│   ├── fixtures/
│   └── conftest.py
├── pyproject.toml
├── requirements.txt
├── alembic.ini
└── Dockerfile
```

---

## 3. Frontend Structure

```text
frontend/
├── src/
│   ├── app/
│   │   ├── router.tsx
│   │   ├── providers.tsx
│   │   └── store.ts
│   │
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── LoginPage.tsx
│   │   │   └── ForgotPasswordPage.tsx
│   │   ├── dashboard/
│   │   │   └── DashboardPage.tsx
│   │   ├── projects/
│   │   │   ├── ProjectListPage.tsx
│   │   │   └── ProjectDetailsPage.tsx
│   │   ├── incidents/
│   │   │   ├── IncidentListPage.tsx
│   │   │   ├── IncidentDetailsPage.tsx
│   │   │   └── CreateIncidentPage.tsx
│   │   ├── analysis/
│   │   │   ├── AnalysisProgressPage.tsx
│   │   │   └── AnalysisResultPage.tsx
│   │   ├── notifications/
│   │   │   └── NotificationCenterPage.tsx
│   │   ├── reports/
│   │   │   └── IncidentReportPage.tsx
│   │   ├── history/
│   │   │   └── HistoryPage.tsx
│   │   ├── evaluation/
│   │   │   └── EvaluationPage.tsx
│   │   └── settings/
│   │       └── SettingsPage.tsx
│   │
│   ├── features/
│   │   ├── auth/
│   │   ├── projects/
│   │   ├── uploads/
│   │   ├── incidents/
│   │   ├── analysis/
│   │   ├── evidence/
│   │   ├── recommendations/
│   │   ├── notifications/
│   │   ├── reports/
│   │   └── history/
│   │
│   ├── components/
│   │   ├── layout/
│   │   ├── navigation/
│   │   ├── forms/
│   │   ├── cards/
│   │   ├── tables/
│   │   ├── dialogs/
│   │   ├── charts/
│   │   ├── feedback/
│   │   └── common/
│   │
│   ├── services/
│   │   ├── apiClient.ts
│   │   ├── authApi.ts
│   │   ├── projectApi.ts
│   │   ├── incidentApi.ts
│   │   ├── analysisApi.ts
│   │   ├── notificationApi.ts
│   │   └── reportApi.ts
│   │
│   ├── hooks/
│   ├── types/
│   ├── schemas/
│   ├── utils/
│   ├── constants/
│   ├── assets/
│   ├── styles/
│   ├── App.tsx
│   └── main.tsx
│
├── public/
├── tests/
├── package.json
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

---

## 4. Documentation Structure

```text
docs/
├── MASTER_ARCHITECTURE.md
├── SYSTEM_ARCHITECTURE.md
├── PROJECT_STRUCTURE.md
├── PROJECT_CONSTITUTION.md
├── IMPLEMENTATION_ROADMAP.md
├── CUSTOMER_JOURNEY.md
├── INCIDENT_WORKFLOW.md
├── DATABASE.md
├── API_SPECIFICATION.md
├── AI_ARCHITECTURE.md
├── DATASET_SPECIFICATION.md
├── SECURITY.md
├── TESTING_STRATEGY.md
├── DEPLOYMENT.md
└── RESEARCH_EVALUATION.md
```

---

## 5. Dataset Structure

```text
datasets/
├── raw/
│   ├── github_actions/
│   ├── terraform/
│   ├── aws/
│   ├── backend/
│   └── frontend/
├── processed/
│   ├── train.jsonl
│   ├── validation.jsonl
│   └── test.jsonl
├── labelled/
├── synthetic/
├── metadata/
├── scripts/
└── README.md
```

---

## 6. Knowledge Base Structure

```text
knowledge_base/
├── github_actions/
├── terraform/
├── aws/
├── docker/
├── kubernetes/
├── security/
├── troubleshooting/
├── processed/
├── embeddings/
└── README.md
```

---

## 7. Infrastructure Structure

```text
infrastructure/
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── nginx.conf
├── terraform/
│   ├── modules/
│   ├── environments/
│   │   ├── development/
│   │   ├── staging/
│   │   └── production/
│   └── README.md
├── monitoring/
└── scripts/
```

---

## 8. GitHub Structure

```text
.github/
├── workflows/
│   ├── backend-ci.yml
│   ├── frontend-ci.yml
│   ├── test.yml
│   ├── security-scan.yml
│   └── deploy.yml
├── ISSUE_TEMPLATE/
└── pull_request_template.md
```

---

## 9. Core Responsibility Rules

### API Layer

Handles HTTP requests, validation, authentication, response formatting, and error mapping.

### Application Layer

Coordinates use cases and transactions. It may call repositories, AI components, notification providers, and report generators.

### Domain Layer

Contains framework-independent entities, interfaces, enums, exceptions, and business rules.

### Infrastructure Layer

Contains SQLAlchemy, PostgreSQL, file storage, notification integrations, external APIs, report generation, and provider implementations.

### AI Layer

Contains preprocessing, classification, evidence extraction, RAG, LLM reasoning, recommendations, and evaluation.

### Frontend

Presents incidents, analysis results, notifications, evidence, remediation steps, history, and reports to the customer.

---

## 10. Main Customer-Centred Domain Flow

```text
User
  ↓
Project
  ↓
Pipeline Run
  ↓
Incident
  ├── Uploaded Files
  ├── Prediction
  ├── Evidence Items
  ├── Root Cause
  ├── Recommendations
  ├── Notifications
  ├── Incident Notes
  └── Incident Reports
```

---

## 11. MSc MVP Scope

The MSc MVP should implement:

- User authentication
- Project creation
- Manual artifact upload
- GitHub Actions log analysis
- Terraform analysis
- Incident creation
- In-app notifications
- Failure classification
- Evidence extraction
- RAG-based documentation retrieval
- LLM root-cause reasoning
- Step-by-step remediation
- Incident history
- Incident resolution
- PDF or Markdown incident report generation

---

## 12. Future Commercial Scope

Future versions may add:

- Automatic GitHub webhook ingestion
- GitLab, Jenkins, and Azure DevOps
- Slack, Teams, and email notifications
- Multi-tenant organizations
- Team collaboration
- Billing and subscriptions
- Automated remediation
- Self-healing pipelines
- Predictive deployment risk
- Kubernetes, Docker, Pulumi, Azure, and GCP providers

---

## 13. Architecture Rule

The project must remain a modular monolith for the MSc MVP.

Microservices should only be introduced when operational scale or independent deployment justifies the added complexity.