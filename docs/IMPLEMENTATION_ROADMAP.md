# DevGuard AI - Implementation Roadmap

Version: 1.0

Status: Active Development

Project Type:
MSc Dissertation + Commercial SaaS Platform

---

# 1. Project Goal

Build an enterprise-grade AI-powered DevOps Intelligence Platform capable of:

• Analysing CI/CD failures
• Analysing Infrastructure-as-Code
• Extracting evidence
• Performing AI reasoning
• Generating remediation recommendations

This roadmap defines the order in which every module must be implemented.

The order must not change without approval.

---

# 2. Development Strategy

The project is divided into independent modules.

Each module must:

✔ Be completed
✔ Be tested
✔ Be documented
✔ Be reviewed

before the next module starts.

Never work on multiple unfinished modules simultaneously.

---

# 3. Project Phases

Phase 1
Project Foundation

↓

Phase 2
Dataset

↓

Phase 3
Machine Learning

↓

Phase 4
Backend

↓

Phase 5
AI Engine

↓

Phase 6
Frontend

↓

Phase 7
Integration

↓

Phase 8
Evaluation

↓

Phase 9
Deployment

---

# PHASE 1
PROJECT FOUNDATION

Status:
Not Started

Goal

Build the project structure.

Tasks

Create repository

Create folder structure

Docker

Backend skeleton

Frontend skeleton

Environment configuration

Logging

Configuration management

Health API

Database connection

Definition of Done

Project runs successfully.

Health endpoint returns 200.

Docker starts successfully.

---

# PHASE 2
DATASET

Status:
Not Started

Goal

Build a labelled dataset.

Tasks

Design dataset schema

Create dataset folders

Collect GitHub Actions logs

Collect Terraform files

Label failures

Clean logs

Extract metadata

Generate dataset

Split dataset

Validate dataset

Output

train.jsonl

validation.jsonl

test.jsonl

Definition of Done

Dataset passes validation.

No duplicate records.

Labels complete.

---

# PHASE 3
MACHINE LEARNING

Status:
Not Started

Goal

Train failure classifier.

Tasks

Preprocessing

Feature extraction

TF-IDF

Train Logistic Regression

Train Random Forest

Evaluate models

Save model

Version model

Definition of Done

Model accuracy evaluated.

Model saved.

Prediction API ready.

---

# PHASE 4
BACKEND

Status:
Not Started

Goal

Create REST API.

Tasks

Authentication

Upload API

Analysis API

History API

Evaluation API

Database repositories

Services

Validation

Definition of Done

Swagger complete.

Endpoints tested.

---

# PHASE 5
AI ENGINE

Status:
Not Started

Goal

Build the intelligence pipeline.

Tasks

Evidence Extraction

RAG

Vector database

Prompt templates

LLM integration

Recommendation generator

Confidence scoring

Definition of Done

Pipeline generates:

Root Cause

Evidence

Recommendation

Confidence

---

# PHASE 6
FRONTEND

Status:
Not Started

Goal

Build enterprise dashboard.

Pages

Login

Dashboard

Upload

Analysis

Evidence Viewer

Recommendation

History

Evaluation

Settings

Definition of Done

Responsive UI.

Connected to backend.

---

# PHASE 7
SYSTEM INTEGRATION

Status:
Not Started

Goal

Connect everything.

Tasks

Upload

↓

Backend

↓

ML

↓

RAG

↓

LLM

↓

Database

↓

Frontend

Definition of Done

End-to-end workflow works.

---

# PHASE 8
MODEL EVALUATION

Status:
Not Started

Goal

Evaluate the AI.

Metrics

Accuracy

Precision

Recall

F1 Score

Confusion Matrix

Top-K Accuracy

Response Time

Definition of Done

Evaluation report generated.

---

# PHASE 9
DEPLOYMENT

Status:
Not Started

Goal

Deploy DevGuard AI.

Tasks

Docker

Docker Compose

GitHub Actions

Terraform

AWS

Monitoring

Definition of Done

Application deployed successfully.

---

# 4. Module Breakdown

Module 1

Foundation

Dependencies

None

Estimated Time

1 Day

Priority

Critical

--------------------------------------------------

Module 2

Database

Dependencies

Foundation

Estimated Time

1 Day

Priority

Critical

--------------------------------------------------

Module 3

Authentication

Dependencies

Database

Estimated Time

1 Day

Priority

High

--------------------------------------------------

Module 4

File Upload

Dependencies

Authentication

Estimated Time

1 Day

Priority

Critical

--------------------------------------------------

Module 5

Dataset Pipeline

Dependencies

Upload

Estimated Time

2 Days

Priority

Critical

--------------------------------------------------

Module 6

Machine Learning

Dependencies

Dataset

Estimated Time

2 Days

Priority

Critical

--------------------------------------------------

Module 7

Evidence Extraction

Dependencies

ML

Estimated Time

1 Day

Priority

Critical

--------------------------------------------------

Module 8

RAG

Dependencies

Evidence Extraction

Estimated Time

1 Day

Priority

Critical

--------------------------------------------------

Module 9

LLM Reasoning

Dependencies

RAG

Estimated Time

1 Day

Priority

Critical

--------------------------------------------------

Module 10

Analysis Engine

Dependencies

LLM

Estimated Time

1 Day

Priority

Critical

--------------------------------------------------

Module 11

Frontend

Dependencies

Analysis Engine

Estimated Time

2 Days

Priority

High

--------------------------------------------------

Module 12

Evaluation

Dependencies

Frontend

Estimated Time

1 Day

Priority

High

--------------------------------------------------

Module 13

Deployment

Dependencies

Evaluation

Estimated Time

1 Day

Priority

Medium

---

# 5. Development Rules

Every module must follow the same workflow.

Planning

↓

Architecture

↓

Implementation

↓

Unit Tests

↓

Integration Tests

↓

Documentation

↓

Review

↓

Approval

↓

Next Module

No shortcuts.

---

# 6. Git Workflow

Feature Branch

↓

Development

↓

Pull Request

↓

Review

↓

Merge

↓

Tag Release

Commit messages

feat:

fix:

refactor:

test:

docs:

chore:

---

# 7. Quality Gates

Before closing a module:

✓ Ruff passes

✓ MyPy passes

✓ Unit tests pass

✓ Integration tests pass

✓ API documented

✓ README updated

✓ No TODOs

✓ No warnings

---

# 8. Documentation Checklist

Every completed module must contain

Architecture explanation

README

API examples

Screenshots (if UI)

Usage guide

Configuration guide

Known limitations

Future improvements

---

# 9. Daily Development Workflow

Before starting work

Read:

PROJECT_CONSTITUTION.md

MASTER_ARCHITECTURE.md

IMPLEMENTATION_ROADMAP.md

Understand today's module.

Implement only today's module.

Test it.

Commit it.

Update roadmap.

---

# 10. Progress Tracker

| Module | Status | Progress |
|---------|--------|----------|
| Foundation | ⬜ | 0% |
| Database | ⬜ | 0% |
| Authentication | ⬜ | 0% |
| Upload | ⬜ | 0% |
| Dataset | ⬜ | 0% |
| Machine Learning | ⬜ | 0% |
| Evidence Extraction | ⬜ | 0% |
| RAG | ⬜ | 0% |
| LLM | ⬜ | 0% |
| Analysis Engine | ⬜ | 0% |
| Frontend | ⬜ | 0% |
| Evaluation | ⬜ | 0% |
| Deployment | ⬜ | 0% |

---

# 11. Definition of Project Completion

The project is complete only when:

✓ All modules are finished.

✓ The application runs end-to-end.

✓ A user can upload a CI/CD log, workflow YAML, and Terraform file.

✓ The AI classifies the failure.

✓ Evidence is extracted.

✓ RAG retrieves relevant documentation.

✓ The LLM generates a root cause and remediation.

✓ Results are stored in the database.

✓ Results are displayed in the frontend.

✓ Evaluation metrics are available.

✓ The system is documented.

✓ The project is ready for dissertation demonstration.

---

# 12. Long-Term Commercial Roadmap

After the MSc, the product will evolve with:

Version 2.0
- GitLab CI
- Jenkins
- Azure DevOps
- Docker analysis
- Kubernetes analysis

Version 3.0
- Predictive deployment risk
- Cloud cost optimization
- Security scanning
- Multi-tenant SaaS
- Organization management
- Billing and subscriptions

Version 4.0
- AI DevOps Copilot
- Self-healing pipelines
- Intelligent deployment recommendations
- Enterprise integrations