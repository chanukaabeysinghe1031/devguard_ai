# DevGuard AI - Project Constitution

Version: 1.0

Status: Approved

Last Updated: July 2026

---

# 1. Project Vision

DevGuard AI is an AI-powered DevOps Intelligence Platform designed to automatically analyse CI/CD pipeline failures, Infrastructure-as-Code (IaC), and deployment configurations to identify root causes, extract supporting evidence, and generate intelligent remediation recommendations.

The project has two objectives:

1. Successfully complete an MSc Advanced Software Engineering dissertation.

2. Become a production-ready commercial SaaS platform after the dissertation.

Every design decision should satisfy both objectives.

---

# 2. Core Principles

Every part of this project must follow these principles.

• Clean Architecture

• SOLID Principles

• Separation of Concerns

• High Maintainability

• Extensibility

• Scalability

• Testability

• Security First

• Reusability

Never sacrifice architecture for speed.

---

# 3. Development Philosophy

This project is NOT a university prototype.

It is a commercial SaaS platform that will first be delivered as an MSc dissertation.

Always build software that could be deployed to production.

---

# 4. Golden Rules

Rule 1

Never generate large amounts of code at once.

Rule 2

Always explain the design before writing code.

Rule 3

Every module must compile successfully before moving to the next module.

Rule 4

Every module must have tests.

Rule 5

Every module must be documented.

Rule 6

Never duplicate business logic.

Rule 7

Never hardcode configuration.

Rule 8

Never expose secrets.

Rule 9

Always think about future scalability.

Rule 10

Always write production-quality code.

---

# 5. Implementation Strategy

The project will be built module by module.

Each module must be completed before the next one starts.

Modules are:

Module 1
Foundation

Module 2
Database

Module 3
Authentication

Module 4
File Upload

Module 5
Dataset Pipeline

Module 6
Machine Learning

Module 7
Evidence Extraction

Module 8
RAG

Module 9
LLM Reasoning

Module 10
Analysis Engine

Module 11
Frontend

Module 12
Evaluation

Module 13
Deployment

Never skip module order unless explicitly instructed.

---

# 6. Technology Stack

Backend

Python 3.11

FastAPI

SQLAlchemy

Alembic

Pydantic

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

Sentence Transformers

RAG

LangChain

LLM

OpenAI API

Infrastructure

Docker

GitHub Actions

Terraform

AWS

---

# 7. Architecture Rules

The project follows Clean Architecture.

Layers are:

Presentation

Application

Domain

Infrastructure

Dependencies always point inward.

Domain must never depend on FastAPI, SQLAlchemy, React, or any framework.

---

# 8. AI Pipeline

Every analysis follows exactly this pipeline.

Upload

↓

Validation

↓

Secret Masking

↓

Preprocessing

↓

Feature Extraction

↓

Failure Classification

↓

Evidence Extraction

↓

RAG Retrieval

↓

LLM Reasoning

↓

Recommendation Generation

↓

Database

↓

Frontend

No component should bypass this pipeline.

---

# 9. Supported Platforms

Version 1

GitHub Actions

Terraform

AWS

Future

GitLab CI

Azure DevOps

Jenkins

Docker

Kubernetes

Azure

Google Cloud

The architecture must support future platforms through provider interfaces.

---

# 10. Coding Standards

Every file must follow:

PEP8

Type Hints

Meaningful variable names

Meaningful function names

Small reusable functions

Single Responsibility Principle

No magic numbers

No duplicated logic

Proper logging

Proper exception handling

---

# 11. Error Handling

Never ignore exceptions.

Always:

Log

Wrap

Return meaningful API responses

Never expose stack traces to users.

---

# 12. Logging

Use structured logging.

Never print().

Every error should include:

timestamp

module

function

error

request id (if available)

---

# 13. Security

Always validate uploaded files.

Always mask secrets before storing.

Never store:

AWS Keys

GitHub Tokens

Passwords

Private Keys

Always validate:

File Size

File Type

MIME Type

---

# 14. Database Rules

Every table uses UUID primary keys.

Every table contains timestamps where appropriate.

Never delete important records permanently.

Prefer soft delete if needed.

All database access must go through repositories.

---

# 15. API Standards

REST APIs only.

Version all APIs.

Example

/api/v1/

Every endpoint returns:

Success

OR

Standard Error Response

Never return inconsistent JSON.

---

# 16. Frontend Rules

Always use reusable components.

No duplicated UI.

Dark mode by default.

Responsive.

Enterprise appearance.

Every page must load gracefully.

---

# 17. Machine Learning Rules

Version every model.

Save evaluation metrics.

Never overwrite trained models.

Every prediction stores:

Predicted Class

Confidence

Model Version

Timestamp

---

# 18. RAG Rules

Never call the LLM without retrieval.

Always retrieve relevant documentation first.

Store retrieved document references.

Always cite retrieved evidence internally.

---

# 19. Prompt Engineering Rules

LLM prompts must:

Provide context

Provide retrieved evidence

Provide failure category

Provide platform

Ask for JSON output

Never ask for plain text responses when structured output is required.

---

# 20. Testing Rules

Every module requires:

Unit Tests

Integration Tests

Manual Testing

Critical workflows require end-to-end tests.

---

# 21. Git Rules

Small commits.

Meaningful commit messages.

Never commit:

.env

API Keys

Secrets

Large datasets

Model artifacts

---

# 22. Documentation Rules

Every module requires:

Architecture Notes

README

API Documentation

Configuration Instructions

Usage Examples

No undocumented modules.

---

# 23. Definition of Done

A module is complete only if:

Code compiles.

Tests pass.

Documentation is written.

API works.

Frontend works.

No TODOs remain.

Reviewed by the project architect.

---

# 24. Cursor Behaviour Rules

Cursor is responsible for implementation.

Cursor is NOT responsible for architecture decisions.

Before writing code Cursor must:

Explain what will be built.

Explain why.

Explain dependencies.

Then generate code.

Never generate the entire project at once.

Never simplify architecture.

Never invent APIs.

Never change the database schema without approval.

Always follow this constitution.

---

# 25. AI Assistant Behaviour Rules

The AI assistant acts as:

Senior Software Architect

Senior AI Engineer

Senior Machine Learning Engineer

Senior DevOps Engineer

Senior Backend Engineer

Senior Frontend Engineer

Database Architect

Security Engineer

The AI assistant should recommend improvements before implementation but must not change the agreed architecture without explaining the trade-offs.

---

# 26. Dissertation Alignment

Every implementation must support the research objectives.

RQ1

Failure Classification

RQ2

Evidence Extraction

RQ3

LLM Reasoning and Remediation

RQ4

Evaluation and Performance Measurement

If a feature does not contribute to these research questions or to the commercial vision, reconsider its priority.

---

# 27. Final Principle

Every line of code should satisfy this question:

"Would I be comfortable deploying this to a paying customer?"

If the answer is "No",

then redesign it before implementation.