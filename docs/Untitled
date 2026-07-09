# DevGuard AI – System Architecture

Version: 1.0

Status: Approved

Author: Project Architecture Team

---

# Table of Contents

1. Introduction
2. System Vision
3. High-Level Architecture
4. Architectural Principles
5. System Components
6. Layered Architecture
7. Backend Architecture
8. AI Architecture
9. Frontend Architecture
10. Database Architecture
11. Component Interaction
12. Request Lifecycle
13. AI Analysis Flow
14. Deployment Architecture
15. Security Architecture
16. Logging & Monitoring
17. Scalability Strategy
18. Future Architecture
19. Technology Decisions

---

# 1. Introduction

DevGuard AI is an AI-powered DevOps Intelligence Platform designed to analyse CI/CD pipeline failures, Infrastructure-as-Code (IaC), and deployment configurations using Artificial Intelligence.

The platform automatically:

- analyses pipeline failures
- classifies failure types
- extracts evidence
- retrieves relevant documentation
- performs AI reasoning
- generates remediation recommendations

The architecture is designed for both:

- MSc Dissertation
- Commercial SaaS Product

---

# 2. System Vision

```

                DevGuard AI

     AI DevOps Intelligence Platform

                │

      Upload Pipeline Artifacts

                │

        AI Analysis Engine

                │

      Intelligent Recommendations

                │

        Enterprise Dashboard

```

The system behaves like an AI DevOps Engineer.

---

# 3. High-Level Architecture

```

                   React Frontend

                         │

               REST API (FastAPI)

                         │

          Analysis Orchestration Service

                         │

     ┌──────────┬────────────┬─────────────┐

     │          │            │             │

 Dataset     ML Model      RAG        Database

     │          │            │             │

     └──────────┴────────────┴─────────────┘

                         │

                   LLM Service

                         │

                 Recommendation Engine

```

---

# 4. Architectural Principles

The architecture follows:

- Clean Architecture
- SOLID Principles
- Repository Pattern
- Dependency Injection
- Domain Driven Design (Lightweight)
- Provider Pattern
- API Versioning

Core business logic never depends on frameworks.

---

# 5. Major Components

The platform consists of seven major subsystems.

## Component 1

Frontend

Responsibilities

- User interface
- File uploads
- Dashboard
- Results
- Authentication

---

## Component 2

API Layer

Responsibilities

- REST endpoints
- Validation
- Authentication
- Error handling

---

## Component 3

Analysis Engine

Responsibilities

- Coordinate the entire AI pipeline
- Execute preprocessing
- Call classifier
- Call RAG
- Call LLM
- Save results

---

## Component 4

Machine Learning Engine

Responsibilities

- Feature extraction
- Classification
- Confidence prediction

---

## Component 5

Evidence Engine

Responsibilities

- Extract error lines
- Stack traces
- Terraform snippets
- Configuration evidence

---

## Component 6

Knowledge Engine (RAG)

Responsibilities

- Store documentation
- Retrieve relevant documents
- Build context

---

## Component 7

Recommendation Engine

Responsibilities

- Root cause
- Explanation
- Recommendations
- Preventive actions

---

# 6. Layered Architecture

```

Presentation Layer

↓

API Layer

↓

Application Layer

↓

Domain Layer

↓

Infrastructure Layer

```

### Presentation

React

### API

FastAPI Routers

### Application

Business Services

### Domain

Entities

Interfaces

Business Rules

### Infrastructure

Database

LLM

ML

RAG

External APIs

---

# 7. Backend Architecture

```

backend/

├── api/

├── core/

├── database/

├── domain/

├── services/

├── repositories/

├── ai/

├── ml/

├── rag/

├── preprocessing/

├── evaluation/

├── security/

├── utils/

└── tests/

```

Each folder has a single responsibility.

---

# 8. AI Architecture

```

Upload

↓

Validation

↓

Secret Masking

↓

Cleaning

↓

Metadata Extraction

↓

TF-IDF

↓

Classifier

↓

Evidence Extraction

↓

RAG Retrieval

↓

LLM

↓

Recommendation

↓

Database

↓

Frontend

```

---

# 9. Frontend Architecture

```

React

│

├── Dashboard

├── Upload

├── Analysis

├── Evidence Viewer

├── Recommendation

├── History

├── Evaluation

└── Settings

```

Shared Components

Buttons

Cards

Tables

Dialogs

Forms

Charts

---

# 10. Database Architecture

Main Tables

```

Users

↓

Uploaded Files

↓

Pipeline Runs

↓

Predictions

↓

Evidence

↓

Recommendations

↓

Evaluations

```

Relationships

One User

↓

Many Uploads

↓

Many Pipeline Runs

↓

One Prediction

↓

Many Evidence Items

↓

One Recommendation

---

# 11. Component Communication

```

Frontend

↓

REST API

↓

Application Service

↓

Repositories

↓

PostgreSQL

```

AI Components

```

Application Service

↓

ML

↓

Evidence

↓

RAG

↓

LLM

↓

Recommendation

```

---

# 12. Request Lifecycle

User uploads files.

↓

Upload Service validates files.

↓

Secrets are masked.

↓

Logs are cleaned.

↓

Metadata extracted.

↓

Classifier predicts category.

↓

Evidence extracted.

↓

RAG retrieves documents.

↓

LLM generates reasoning.

↓

Results stored.

↓

Frontend displays results.

---

# 13. AI Sequence Diagram

```

User

↓

Upload

↓

API

↓

Analysis Service

↓

Classifier

↓

Evidence Engine

↓

RAG

↓

LLM

↓

Recommendation

↓

Database

↓

Frontend

```

---

# 14. Deployment Architecture

```

                 Internet

                     │

               Reverse Proxy

                     │

         ┌───────────┴───────────┐

         │                       │

      React App             FastAPI

                                 │

                      PostgreSQL

                                 │

                         ChromaDB

                                 │

                         OpenAI API

```

Development

Docker Compose

Production

AWS

---

# 15. Security Architecture

Authentication

JWT

Authorization

Role-based

Uploads

File validation

Secret masking

Sanitization

Database

Parameterized queries

Environment

Secrets stored in .env

Never committed

---

# 16. Logging

Every request generates

Request ID

Execution Time

Module

Status

Errors

AI Events

Prediction

Confidence

Retrieved Documents

LLM Response Time

---

# 17. Monitoring

System Metrics

CPU

Memory

Disk

Application Metrics

API latency

Prediction latency

LLM latency

Classification accuracy

Error rate

---

# 18. Scalability

Current

Single FastAPI Application

Future

Microservices

Classifier Service

RAG Service

LLM Service

Dataset Service

Evaluation Service

Frontend remains unchanged.

---

# 19. Provider Pattern

Supported providers

```

CICD Provider

├── GitHub Actions

├── GitLab

├── Jenkins

└── Azure DevOps

```

Cloud

```

Cloud Provider

├── AWS

├── Azure

└── GCP

```

IaC

```

IaC Provider

├── Terraform

├── Docker

├── Kubernetes

└── Pulumi

```

---

# 20. Technology Decisions

| Layer | Technology |
|---------|------------|
| Frontend | React + TypeScript |
| Backend | FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| Vector DB | ChromaDB |
| ML | Scikit-learn |
| Embeddings | Sentence Transformers |
| LLM | OpenAI |
| Container | Docker |
| IaC | Terraform |
| CI/CD | GitHub Actions |

---

# 21. Design Decisions

### Why Clean Architecture?

- Easy to test
- Easy to maintain
- Framework-independent
- Long-term scalability

### Why FastAPI?

- High performance
- Automatic Swagger documentation
- Strong typing
- Excellent AI ecosystem

### Why PostgreSQL?

- Mature
- Reliable
- Supports JSONB
- Excellent indexing

### Why ChromaDB?

- Simple setup
- Fast development
- Excellent LangChain integration

### Why TF-IDF + Logistic Regression?

- Fast to train
- Explainable
- Suitable for limited datasets
- Good baseline for research evaluation

---

# 22. Future Evolution

Version 2

- GitLab CI
- Jenkins
- Docker Analysis
- Kubernetes Analysis

Version 3

- Multi-tenant SaaS
- Teams
- Organizations
- Billing
- Predictive Deployment Risk

Version 4

- AI DevOps Copilot
- Self-Healing Pipelines
- Autonomous Infrastructure Optimization

---

# 23. Architecture Success Criteria

The architecture is considered complete when:

✓ Users can upload CI/CD artifacts.

✓ Files are validated and secured.

✓ AI analyses the pipeline.

✓ Failure category is predicted.

✓ Evidence is extracted.

✓ Relevant documentation is retrieved.

✓ LLM produces structured reasoning.

✓ Recommendations are generated.

✓ Results are stored.

✓ Results are displayed in the dashboard.

✓ Every AI decision is explainable.

✓ The platform can be extended to support additional CI/CD platforms without changing the core architecture.