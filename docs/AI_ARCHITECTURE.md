# DevGuard AI - AI Architecture

Version: 1.0

Status: Approved

Last Updated: July 2026

---

# 1. Overview

This document describes the Artificial Intelligence architecture of DevGuard AI.

The AI system is responsible for transforming raw CI/CD pipeline logs and Infrastructure-as-Code (IaC) files into intelligent, explainable remediation recommendations.

Unlike traditional CI/CD monitoring tools, DevGuard AI combines:

- Machine Learning
- Rule-based Processing
- Retrieval-Augmented Generation (RAG)
- Large Language Models (LLMs)

to provide accurate, explainable and actionable failure analysis.

---

# 2. AI Objectives

The AI system must:

✓ Detect CI/CD failures

✓ Classify failure categories

✓ Extract supporting evidence

✓ Retrieve relevant technical documentation

✓ Perform contextual reasoning

✓ Generate remediation recommendations

✓ Estimate confidence scores

✓ Explain every prediction

---

# 3. AI Pipeline Overview

```

User Upload

↓

Validation

↓

Secret Masking

↓

Log Cleaning

↓

Metadata Extraction

↓

Feature Extraction

↓

Failure Classification

↓

Evidence Extraction

↓

Knowledge Retrieval (RAG)

↓

LLM Reasoning

↓

Recommendation Generation

↓

Confidence Scoring

↓

Database Storage

↓

Frontend Display

```

---

# 4. AI Components

The AI engine consists of seven major components.

1. Preprocessing Engine

2. Feature Engineering Engine

3. Classification Engine

4. Evidence Extraction Engine

5. Knowledge Retrieval Engine (RAG)

6. Reasoning Engine (LLM)

7. Recommendation Engine

---

# 5. Preprocessing Engine

Purpose

Prepare uploaded files for AI processing.

Inputs

GitHub Actions Log

Workflow YAML

Terraform Files

Outputs

Cleaned Log

Metadata

Extracted Error Sections

Responsibilities

Remove ANSI characters

Remove timestamps

Remove installation noise

Mask secrets

Normalize whitespace

Extract error blocks

Identify stack traces

---

# 6. Secret Masking Engine

Sensitive information must never reach the AI.

Detect

AWS Keys

GitHub Tokens

Passwords

Bearer Tokens

JWT Tokens

Private Keys

Replace with

```

<REDACTED>

```

This module runs before every AI component.

---

# 7. Metadata Extraction

Extract

Repository

Branch

Commit

Workflow

Job Name

Runner

Operating System

Language

Cloud Provider

Terraform Version

Docker Version

These become structured features.

---

# 8. Feature Engineering

Version 1

TF-IDF

Features

Error Messages

Stack Trace

Command Names

File Names

Terraform Resources

Provider Names

Future

Sentence Embeddings

CodeBERT

Log Embeddings

---

# 9. Failure Classification Engine

Purpose

Predict the failure category.

Version 1

TF-IDF

↓

Logistic Regression

Output

Failure Category

Confidence Score

Supported Categories

Build Failure

Test Failure

Dependency Failure

Configuration Failure

Terraform Failure

Docker Failure

Deployment Failure

AWS Permission Failure

Network Failure

Security Misconfiguration

Unknown Failure

---

# 10. Evidence Extraction Engine

Purpose

Identify log lines supporting the prediction.

Methods

Regex

Pattern Matching

Stack Trace Analysis

Configuration Parsing

Outputs

Relevant Error Lines

Terraform Snippets

Workflow Sections

AWS Errors

Every evidence item receives

Relevance Score

Source Location

Highlight Position

---

# 11. Knowledge Retrieval Engine (RAG)

Purpose

Retrieve documentation before LLM reasoning.

Knowledge Sources

AWS Documentation

Terraform Documentation

GitHub Actions Documentation

Internal Troubleshooting Guides

Known Failure Database

Workflow Best Practices

Storage

ChromaDB

Embedding Model

Sentence Transformers

```

all-MiniLM-L6-v2

```

Retrieval Process

Query

↓

Embedding

↓

Vector Search

↓

Top-k Documents

↓

LLM Context

---

# 12. Prompt Builder

The Prompt Builder combines:

Failure Category

Evidence

Workflow Information

Terraform Information

Retrieved Documents

Metadata

into one structured prompt.

Prompt Rules

Never send raw logs directly.

Always summarize.

Always include retrieved evidence.

Always request JSON output.

---

# 13. LLM Reasoning Engine

Purpose

Generate human-readable analysis.

Input

Evidence

Classification

Retrieved Documents

Metadata

Output

Root Cause

Explanation

Recommendation

Risk Level

Preventive Actions

Future Improvements

Suggested Commands

---

# 14. Recommendation Engine

Generate

Step-by-step Fixes

Terraform Changes

GitHub Actions Fixes

AWS Permission Suggestions

Workflow Improvements

Security Recommendations

Best Practices

Every recommendation should be:

Specific

Actionable

Reproducible

---

# 15. Confidence Scoring

Overall confidence is calculated using multiple signals.

Classifier Confidence

Evidence Quality

Retrieval Similarity

LLM Consistency

Historical Match

Formula (conceptual)

Overall Confidence

=

Weighted Average

This score is displayed to the user.

---

# 16. Explainability

Every prediction must include:

Predicted Category

Confidence

Supporting Evidence

Retrieved Documents

Root Cause

Recommendation

Users must understand WHY the prediction was made.

---

# 17. AI Output Schema

```

{
"failure_category":"",
"confidence":0.94,
"root_cause":"",
"summary":"",
"evidence":[],
"recommendation":[],
"preventive_actions":[],
"future_improvements":[]
}

```

---

# 18. Model Training Pipeline

Dataset

↓

Cleaning

↓

Feature Extraction

↓

Training

↓

Validation

↓

Evaluation

↓

Model Registry

↓

Prediction Service

---

# 19. Model Registry

Every trained model stores

Model Name

Version

Training Date

Dataset Version

Accuracy

Precision

Recall

F1 Score

Training Parameters

Artifact Location

No trained model is overwritten.

---

# 20. Evaluation Metrics

Classification

Accuracy

Precision

Recall

F1 Score

Top-K Accuracy

Confusion Matrix

Evidence

Evidence Precision

Evidence Recall

Average Relevance Score

RAG

Retrieval Precision@K

MRR

Context Relevance

LLM

Recommendation Quality

Root Cause Correctness

Helpfulness Score

Human Evaluation

Latency

Average Response Time

Inference Time

---

# 21. Human Feedback Loop

Users can provide

Correct

Incorrect

Helpful

Not Helpful

Rating

Comment

Future versions may use this feedback for retraining.

---

# 22. Error Handling

If classification fails

↓

Return Unknown Failure

↓

Still perform RAG

↓

Generate best-effort recommendation

↓

Log the incident

The system should never crash because of one failed prediction.

---

# 23. AI Versioning

Every AI release has a version.

Example

AI v1.0

Classifier v1.0

Prompt v1.0

Knowledge Base v1.0

LLM Configuration v1.0

Every prediction stores the AI version.

---

# 24. Future AI Roadmap

Version 2

CodeBERT

DistilBERT

Semantic Search

GitLab Support

Docker Analysis

Version 3

Kubernetes Analysis

CloudFormation

Pulumi

Deployment Risk Prediction

Version 4

Self-Healing Pipelines

Autonomous Deployment Recommendations

Continuous Learning

---

# 25. Mapping to Research Questions

RQ1

How can AI accurately classify CI/CD failures?

Implemented by:

Failure Classification Engine

---

RQ2

How can AI extract meaningful evidence from logs and IaC?

Implemented by:

Evidence Extraction Engine

Metadata Extraction

---

RQ3

How can Retrieval-Augmented Generation and LLMs improve root cause analysis and remediation?

Implemented by:

Knowledge Retrieval Engine

Prompt Builder

LLM Reasoning Engine

Recommendation Engine

---

RQ4

How effective is the proposed AI approach compared with baseline techniques?

Implemented by:

Evaluation Framework

Model Registry

Metrics Dashboard

Human Feedback

---

# 26. AI Design Principles

The AI must always be:

Explainable

Reproducible

Secure

Modular

Scalable

Observable

Extensible

Production Ready

No AI component should operate as a black box.

Every decision must be traceable through evidence, retrieved documents, model confidence and generated reasoning.

---

# 27. Definition of Done

The AI architecture is complete only when:

✓ Logs are preprocessed correctly.

✓ Secrets are masked.

✓ Metadata is extracted.

✓ Failure category is predicted.

✓ Evidence is extracted.

✓ Relevant documents are retrieved.

✓ LLM generates a structured response.

✓ Confidence score is calculated.

✓ Results are stored.

✓ Results are displayed in the frontend.

✓ Evaluation metrics are available.

✓ Every prediction is explainable.
