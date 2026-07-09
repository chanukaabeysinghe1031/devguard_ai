# DevGuard AI - Master Architecture Document

Version: 1.0

Status: ARCHITECTURE FROZEN

Project Type:
MSc Advanced Software Engineering Dissertation
+
Commercial SaaS Foundation

Last Updated:
July 2026

---

# Document Purpose

This document is the **single source of truth** for the DevGuard AI project.

Every architectural decision must originate from this document.

All other documents extend this document.

If conflicts exist between documents,

**MASTER_ARCHITECTURE.md always takes precedence.**

---

# Project Vision

DevGuard AI is an AI-powered DevOps Intelligence Platform capable of automatically analysing CI/CD failures, Infrastructure-as-Code (IaC), and deployment configurations to identify root causes, extract evidence, retrieve relevant knowledge, and generate intelligent remediation recommendations.

The project serves two purposes:

1. MSc Dissertation
2. Commercial SaaS Product

The architecture must satisfy both.

---

# Version Strategy

## Version 1.0 (MSc Implementation)

Supported Platforms

- GitHub Actions
- Terraform
- AWS

Implemented AI Features

- Failure Classification
- Evidence Extraction
- RAG
- LLM Reasoning
- Recommendation Generation

Implemented Frontend

- Login
- Dashboard
- Upload
- Analysis
- Evidence Viewer
- Recommendation Viewer
- Evaluation
- History

Implemented Backend

- REST API
- PostgreSQL
- ChromaDB
- FastAPI

---

## Version 2.0

Future

- GitLab CI
- Jenkins
- Azure DevOps
- Docker Analysis
- Kubernetes Analysis

---

## Version 3.0

Future

- Multi-Tenant SaaS
- Organizations
- Billing
- Team Management
- Cloud Cost Analysis

---

## Version 4.0

Future

- AI DevOps Copilot
- Predictive Deployment Risk
- Self-Healing Pipelines
- Continuous Learning

---

# Architecture Overview

The system consists of six major subsystems.

```

React Frontend

↓

FastAPI Backend

↓

Analysis Engine

↓

Machine Learning Engine

↓

Knowledge Engine (RAG)

↓

LLM Recommendation Engine

↓

Database

```

---

# Architecture Documents

The complete architecture is divided into specialised documents.

| Document | Purpose |
|----------|---------|
| PROJECT_CONSTITUTION.md | Project rules and development standards |
| IMPLEMENTATION_ROADMAP.md | Development roadmap |
| SYSTEM_ARCHITECTURE.md | Complete software architecture |
| AI_ARCHITECTURE.md | AI pipeline |
| DATASET_SPECIFICATION.md | Dataset design |
| DATABASE.md | Database schema |
| API_SPECIFICATION.md | REST API specification |
| PROJECT_STRUCTURE.md | Folder structure and conventions |

This document should always be read first.

---

# Development Principles

Every module must follow

- Clean Architecture

- SOLID

- Repository Pattern

- Dependency Injection

- API Versioning

- Security First

- Explainable AI

---

# Technology Stack

Backend

Python 3.11

FastAPI

SQLAlchemy

Alembic

Frontend

React

TypeScript

Vite

Tailwind CSS

Database

PostgreSQL

Vector Database

ChromaDB

Machine Learning

Scikit-learn

Embeddings

Sentence Transformers

LLM

OpenAI API

Infrastructure

Docker

GitHub Actions

Terraform

AWS

---

# AI Pipeline

The AI pipeline is fixed.

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

Failure Classification

↓

Evidence Extraction

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

No component may bypass this pipeline.

---

# Current Project Status

Architecture

✅ Complete

Documentation

✅ Complete

Dataset

⬜ Not Started

Machine Learning

⬜ Not Started

Backend

⬜ Not Started

Frontend

⬜ Not Started

Deployment

⬜ Not Started

---

# Development Workflow

Every module follows the same lifecycle.

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

---

# Module Order

Module 1

Foundation

↓

Module 2

Database

↓

Module 3

Authentication

↓

Module 4

Upload

↓

Module 5

Dataset

↓

Module 6

Machine Learning

↓

Module 7

Evidence Extraction

↓

Module 8

RAG

↓

Module 9

LLM

↓

Module 10

Analysis Engine

↓

Module 11

Frontend

↓

Module 12

Evaluation

↓

Module 13

Deployment

The order must not change.

---

# Definition of Architecture Freeze

The following components are frozen for Version 1.0.

Technology Stack

Database Design

Folder Structure

AI Pipeline

Failure Categories

REST API Version

Dataset Schema

No architectural changes should be made unless approved.

---

# Research Mapping

RQ1

Failure Classification

Implemented by

Machine Learning Engine

---

RQ2

Evidence Extraction

Implemented by

Evidence Engine

---

RQ3

Root Cause Analysis

Implemented by

RAG

Prompt Builder

LLM

Recommendation Engine

---

RQ4

Evaluation

Implemented by

Evaluation Module

---

# Commercial Vision

After successful completion of the MSc,

DevGuard AI will evolve into a commercial SaaS platform.

Future commercial features include:

- Multi-platform CI/CD support
- Enterprise authentication
- Organization management
- Team collaboration
- Billing
- API marketplace
- AI DevOps Copilot
- Predictive deployment analysis
- Self-healing pipelines

The Version 1 architecture has been designed to support these future capabilities without requiring major redesign.

---

# Rules for Cursor

Cursor must always read the following documents before implementing any module:

1. MASTER_ARCHITECTURE.md

2. PROJECT_CONSTITUTION.md

3. IMPLEMENTATION_ROADMAP.md

4. Relevant architecture document for the current module

Cursor must never:

- Change the architecture.
- Add new technologies.
- Modify the database schema.
- Invent new APIs.
- Skip module order.

If a change appears necessary, Cursor must explain the reason and wait for approval before implementing it.

---

# Definition of Success

The project is considered successful when:

✓ Users can upload CI/CD logs.

✓ Users can upload workflow YAML files.

✓ Users can upload Terraform files.

✓ The system classifies failures.

✓ Evidence is extracted.

✓ Relevant documentation is retrieved.

✓ The LLM generates explainable recommendations.

✓ Results are stored.

✓ Results are displayed in the dashboard.

✓ Evaluation metrics are available.

✓ The implementation satisfies the MSc research objectives.

✓ The architecture is suitable for future commercial SaaS development.

---

# Final Principle

DevGuard AI is not just an academic prototype.

Every design decision should answer the following question:

> "Can this architecture grow into a production-grade SaaS platform without major redesign?"

If the answer is **No**, redesign before implementation.
