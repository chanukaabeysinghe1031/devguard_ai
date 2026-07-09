# DevGuard AI - Dataset Specification

Version: 1.0

Status: Approved

Last Updated: July 2026

---

# 1. Purpose

This document defines the complete dataset specification for DevGuard AI.

The dataset is the foundation of the AI engine and supports:

• Failure Classification

• Evidence Extraction

• Root Cause Analysis

• Retrieval Augmented Generation (RAG)

• Model Evaluation

Every dataset record must follow this specification.

---

# 2. Dataset Objectives

The dataset should enable the AI to:

✓ Classify CI/CD failures

✓ Extract important evidence

✓ Identify root causes

✓ Retrieve relevant documentation

✓ Generate remediation recommendations

✓ Evaluate model performance

---

# 3. Dataset Sources

Version 1 will use only public data.

Sources include:

GitHub Actions

Public GitHub Repositories

Terraform Open Source Repositories

AWS Documentation

Terraform Documentation

GitHub Actions Documentation

Public DevOps Knowledge Bases

Stack Overflow (reference only)

Official documentation should always be preferred over community content when building the RAG knowledge base.

---

# 4. Supported Platforms

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

---

# 5. Failure Categories

Every dataset record belongs to one category.

| ID | Category | Description |
|----|----------|-------------|
| FC001 | Build Failure | Compilation or build process failed |
| FC002 | Test Failure | Unit, integration or acceptance test failure |
| FC003 | Dependency Failure | Missing or incompatible dependencies |
| FC004 | Configuration Failure | Invalid YAML or configuration |
| FC005 | Terraform Failure | Terraform syntax or validation error |
| FC006 | Docker Failure | Docker build or runtime failure |
| FC007 | Deployment Failure | Deployment pipeline failure |
| FC008 | AWS Permission Failure | IAM or AWS permission issue |
| FC009 | Network Failure | Connection, timeout or DNS issue |
| FC010 | Security Misconfiguration | Secrets or security policy issue |
| FC011 | Unknown Failure | Unable to classify |

---

# 6. Dataset Structure

Each sample represents one failed pipeline execution.

One sample equals one JSON object.

---

# 7. Dataset Schema

```json
{
  "id": "",
  "repository": "",
  "repository_url": "",
  "platform": "",
  "workflow_name": "",
  "job_name": "",
  "branch": "",
  "commit_hash": "",
  "workflow_file": "",
  "terraform_files": [],
  "raw_log": "",
  "cleaned_log": "",
  "failure_category": "",
  "root_cause": "",
  "evidence": [],
  "recommendation": "",
  "severity": "",
  "source_documents": [],
  "created_at": ""
}
```

---

# 8. Required Fields

Every record MUST contain:

id

platform

raw_log

cleaned_log

failure_category

root_cause

evidence

recommendation

---

# 9. Optional Fields

repository

workflow_name

branch

terraform_files

commit_hash

severity

metadata

These improve future models but are not mandatory.

---

# 10. Folder Structure

```
dataset/

raw/

github_actions/

terraform/

aws/

processed/

train/

validation/

test/

metadata/

documentation/

scripts/
```

---

# 11. Naming Convention

```
GA_000001.json

GA_000002.json

TF_000001.json

AWS_000001.json
```

Prefixes:

GA

TF

AWS

---

# 12. File Format

Primary

JSONL

One JSON object per line.

Secondary

CSV

Only for manual inspection.

Never use Excel as the source of truth.

---

# 13. Dataset Lifecycle

Collect

↓

Validate

↓

Mask Secrets

↓

Clean Logs

↓

Extract Metadata

↓

Assign Labels

↓

Quality Check

↓

Split Dataset

↓

Train Models

---

# 14. Secret Masking

Before storing logs remove:

AWS Access Keys

GitHub Tokens

Passwords

Private Keys

JWT Tokens

Bearer Tokens

Email Addresses

IP Addresses (optional)

No sensitive information should remain.

---

# 15. Log Cleaning

Remove:

ANSI colours

Progress bars

Duplicate lines

Installation noise

Long download logs

Keep:

Errors

Warnings

Stack traces

Failed commands

File names

Line numbers

Terraform errors

AWS errors

---

# 16. Evidence Rules

Evidence must directly support the root cause.

Good evidence:

```
Module not found

Error: AccessDenied

Terraform validation failed

Connection timeout
```

Bad evidence:

```
Downloading...

Installing...

Build started...
```

---

# 17. Root Cause Rules

Root causes must be concise.

Good

Missing npm dependency

Invalid Terraform variable

Missing IAM permission

Incorrect YAML syntax

Bad

Build failed

Something went wrong

Unknown issue

---

# 18. Recommendation Rules

Recommendations should be actionable.

Good

Install missing dependency

Correct provider version

Grant IAM permission

Update workflow YAML

Bad

Check your code

Retry later

Unknown solution

---

# 19. Dataset Validation

Every sample is checked for:

Missing fields

Duplicate IDs

Duplicate logs

Invalid labels

Empty evidence

Empty recommendations

Unmasked secrets

Invalid JSON

---

# 20. Dataset Split

Train

70%

Validation

15%

Test

15%

Split should preserve class distribution.

Use stratified sampling where possible.

---

# 21. Model Input

Classifier receives:

cleaned_log

Feature extraction uses:

TF-IDF

Future:

Sentence Embeddings

Transformer Embeddings

---

# 22. RAG Documents

Store separately from training data.

Knowledge Base includes:

AWS Docs

Terraform Docs

GitHub Actions Docs

Known fixes

Internal troubleshooting guides

Never mix RAG documents with labelled training data.

---

# 23. Dataset Versioning

Every release must be versioned.

Example

v1.0

v1.1

v2.0

Never overwrite previous datasets.

---

# 24. Dataset Quality Metrics

Measure:

Duplicate percentage

Missing labels

Average log length

Category distribution

Evidence completeness

Recommendation completeness

Secret masking success

---

# 25. Ethics

Only public repositories.

Never collect private repositories.

Respect repository licenses.

Do not redistribute copyrighted logs without permission.

Always remove sensitive information.

---

# 26. Future Improvements

Future versions may include:

GitLab CI

Azure DevOps

Jenkins

Docker

Kubernetes

CloudFormation

Pulumi

---

# 27. Definition of Done

Dataset is complete only when:

✓ Every record validates.

✓ Every record has a label.

✓ Every record has evidence.

✓ Every record has a root cause.

✓ Every record has a recommendation.

✓ No secrets remain.

✓ Dataset is versioned.

✓ Documentation is updated.

✓ Train/validation/test splits are generated.

✓ Dataset statistics are available.