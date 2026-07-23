# DevGuard AI – DATASET_SPECIFICATION.md

**Version:** 1.0  
**Status:** Proposed Baseline  
**Project:** DevGuard AI  
**Research Context:** MSc Advanced Software Engineering  
**Primary Purpose:** CI/CD failure classification, evidence extraction, RAG-based root-cause analysis, recommendation generation, and research evaluation

---

# 1. Purpose

This document defines the dataset architecture, structure, labeling rules, quality requirements, versioning process, and evaluation design for DevGuard AI.

The dataset supports the following workflow:

```text
Raw CI/CD Failure Artifacts
        ↓
Failure Classification
        ↓
Evidence Extraction
        ↓
Root-Cause Analysis
        ↓
Knowledge Retrieval
        ↓
Recommendation Generation
        ↓
Research Evaluation
```

The specification is designed for a reproducible MSc research project while remaining extensible for the future DevGuard AI product.

---

# 2. Dataset Objectives

The dataset should allow DevGuard AI to learn and evaluate:

1. Which failure category best describes a CI/CD incident.
2. Which log lines or configuration fragments provide the strongest evidence.
3. Which technical component and pipeline stage failed.
4. What the likely root cause is.
5. Which remediation and prevention steps are appropriate.
6. Whether retrieved technical documentation supports the explanation.
7. Whether the AI output is correct, grounded, useful, safe, and actionable.

---

# 3. Initial Scope

## 3.1 Supported Sources

The first dataset version should focus on:

- GitHub Actions workflow logs
- Terraform command output and error logs
- GitHub Actions YAML files
- Terraform `.tf` and `.tfvars` files
- Related deployment and infrastructure metadata

## 3.2 Technical Scope

Initial priority:

- GitHub Actions
- Terraform
- AWS
- Docker-related CI failures
- General build, test, configuration, and dependency failures

## 3.3 Future Scope

Future versions may include:

- GitLab CI
- Jenkins
- Azure DevOps
- Kubernetes events and logs
- Helm and Argo CD failures
- Docker runtime logs
- AWS CloudWatch
- Azure Monitor
- GCP Cloud Logging

---

# 4. Dataset Tasks

## 4.1 Failure Classification

Input:

```text
Sanitized pipeline log
+
Optional metadata
+
Optional configuration files
```

Output:

```text
Primary failure category
+
Optional secondary category
```

## 4.2 Evidence Extraction

Input:

```text
Log or configuration artifact
```

Output:

```text
Relevant line ranges
Evidence type
Importance
Explanation
```

## 4.3 Root-Cause Evaluation

Input:

```text
Failure artifact
+
Evidence
+
Retrieved documentation
```

Expected output:

```text
Reference root-cause explanation
```

## 4.4 Recommendation Evaluation

Input:

```text
Confirmed failure category
+
Root cause
+
Evidence
```

Expected output:

```text
Reference remediation steps
Verification steps
Prevention guidance
Risk level
```

## 4.5 Retrieval Evaluation

Input:

```text
Incident retrieval query
```

Expected output:

```text
Relevant knowledge document chunks
```

---

# 5. Dataset Components

DevGuard AI should maintain separate but linked datasets.

## 5.1 Failure Dataset

Used for classification and containing:

- Logs
- Configuration artifacts
- Labels
- Metadata
- Source provenance
- Dataset split

## 5.2 Evidence Dataset

Used for evidence extraction evaluation and containing:

- Sanitized file content
- Evidence spans
- Line numbers
- Evidence types
- Importance labels

## 5.3 Root-Cause Dataset

Used for explanation evaluation and containing:

- Confirmed root cause
- Technical explanation
- Affected component
- Failed operation
- Impact
- Acceptable alternative interpretations

## 5.4 Recommendation Dataset

Used for remediation evaluation and containing:

- Ordered fix steps
- Verification steps
- Prevention steps
- Risk and difficulty labels

## 5.5 Knowledge Base Dataset

Used for retrieval-augmented generation and containing:

- Official technical documentation
- Chunked content
- Metadata
- Version information
- Embedding references

---

# 6. Data Sources

## 6.1 Public Open-Source Sources

Potential sources include:

- Public GitHub repositories with failed workflow runs
- Public Terraform projects
- Public issue reports containing CI/CD failures
- Public pull requests discussing pipeline failures
- Public example projects that can be safely reproduced

## 6.2 Official Documentation

For the RAG knowledge base:

- GitHub Actions documentation
- Terraform documentation
- AWS documentation
- Docker documentation

## 6.3 Controlled Reproduction

Failures may be reproduced in a controlled test environment.

Examples:

- Missing dependency
- Invalid YAML
- Failing unit test
- Missing AWS permission
- Invalid Terraform provider configuration
- Terraform syntax error
- Docker build failure
- Simulated timeout

## 6.4 Synthetic Data

Synthetic data may be used to:

- Increase examples for rare classes
- Create controlled variations of real failures
- Test robustness
- Create adversarial or negative examples

Synthetic data must be clearly marked and must not dominate the final test set.

## 6.5 User-Provided Data

Future customer logs may be used only with:

- Explicit consent
- Secret redaction
- Privacy controls
- Retention policies
- Ethics approval where required

---

# 7. Provenance Requirements

Every sample should record:

- Source type
- Source URL where legally permitted
- Repository name or anonymized identifier
- Collection date
- License or usage basis
- Whether it is public, reproduced, or synthetic
- Whether it was modified
- Whether secrets were detected and removed

Example:

```json
{
  "source_type": "public_github",
  "source_url": "https://github.com/example/project/actions/runs/123",
  "license": "MIT",
  "collection_date": "2026-07-19",
  "is_synthetic": false,
  "is_reproduced": false,
  "was_modified": true
}
```

---

# 8. Failure Taxonomy

## 8.1 Recommended Primary Categories

1. `build_failure`
2. `dependency_failure`
3. `test_failure`
4. `configuration_failure`
5. `authentication_failure`
6. `authorization_failure`
7. `network_failure`
8. `timeout_failure`
9. `terraform_validation_failure`
10. `terraform_plan_failure`
11. `terraform_apply_failure`
12. `deployment_failure`
13. `container_failure`
14. `runtime_failure`
15. `infrastructure_state_failure`
16. `unknown_other`

## 8.2 Recommended MSc Scope

Use 10–12 categories initially. A practical first set is:

1. build_failure
2. dependency_failure
3. test_failure
4. configuration_failure
5. authentication_failure
6. authorization_failure
7. network_failure
8. timeout_failure
9. terraform_validation_failure
10. terraform_plan_failure
11. terraform_apply_failure
12. deployment_failure

## 8.3 Hierarchical Labels

Each sample may include:

```text
Primary category
Secondary category
Affected component
Failure stage
```

Example:

```json
{
  "primary_category": "authorization_failure",
  "secondary_category": "aws_iam_permission",
  "affected_component": "aws_ecs",
  "failure_stage": "deployment"
}
```

---

# 9. Label Definitions

## 9.1 Build Failure

Compilation, packaging, or build-tool failure.

Examples:

- Java compilation error
- TypeScript build error
- Maven or Gradle failure
- Missing build artifact

## 9.2 Dependency Failure

A package, module, or library cannot be installed or resolved.

Examples:

- npm package not found
- Maven dependency resolution failure
- pip dependency conflict
- incompatible package version

## 9.3 Test Failure

A test stage fails because one or more tests do not pass.

Examples:

- Unit test assertion failure
- Integration test failure
- Test runner exits with a non-zero status

## 9.4 Configuration Failure

Invalid or missing configuration.

Examples:

- Invalid YAML
- Missing environment variable
- Wrong workflow syntax
- Incorrect configuration path

## 9.5 Authentication Failure

Identity cannot be verified.

Examples:

- Invalid token
- Expired credentials
- Missing credentials
- Login failure

## 9.6 Authorization Failure

Identity is verified, but permission is denied.

Examples:

- AWS AccessDenied
- GitHub permission denied
- Insufficient IAM role permission

## 9.7 Network Failure

A connection cannot be established or maintained.

Examples:

- DNS resolution failure
- Connection refused
- TLS handshake error
- Unreachable endpoint

## 9.8 Timeout Failure

An operation exceeds the configured time limit.

Examples:

- Job timeout
- API request timeout
- Deployment wait timeout

## 9.9 Terraform Validation Failure

Terraform configuration is invalid before planning.

Examples:

- Syntax error
- Invalid argument
- Missing required field
- Type mismatch

## 9.10 Terraform Plan Failure

Terraform cannot produce a valid execution plan.

Examples:

- Provider read failure
- Invalid reference
- State mismatch discovered during planning

## 9.11 Terraform Apply Failure

A plan exists, but resource application fails.

Examples:

- Cloud API rejection
- Resource conflict
- Permission failure during apply

## 9.12 Deployment Failure

An application or service rollout fails without a more specific applicable root category.

Examples:

- ECS rollout failure
- Failed health checks
- Artifact deployment failure

## 9.13 Unknown or Other

Use only when:

- Evidence is insufficient
- No existing category applies
- Multiple causes cannot be separated

Unknown must not become a default for weak annotation.

---

# 10. Sample Record Schema

Recommended JSONL record:

```json
{
  "sample_id": "gha-000104",
  "incident_group_id": "incident-group-0021",
  "source": {
    "source_type": "public_github",
    "provider": "github_actions",
    "repository": "example/project",
    "source_url": "https://github.com/example/project/actions/runs/123",
    "license": "MIT",
    "collection_date": "2026-07-19",
    "is_synthetic": false,
    "is_reproduced": false
  },
  "artifacts": [
    {
      "artifact_id": "artifact-001",
      "artifact_type": "pipeline_log",
      "original_filename": "github-actions.log",
      "raw_path": "raw/github_actions/gha-000104.log",
      "sanitized_path": "sanitized/github_actions/gha-000104.txt",
      "checksum_sha256": "checksum"
    }
  ],
  "labels": {
    "primary_category": "authorization_failure",
    "secondary_categories": ["aws_iam_permission"],
    "affected_component": "aws_ecs",
    "failure_stage": "deployment",
    "severity": "high"
  },
  "metadata": {
    "workflow_name": "Production Deployment",
    "job_name": "deploy",
    "step_name": "Update ECS service",
    "branch": "main",
    "runner_os": "ubuntu-latest",
    "exit_code": 1,
    "environment": "production"
  },
  "evidence_spans": [
    {
      "artifact_id": "artifact-001",
      "line_start": 443,
      "line_end": 449,
      "evidence_type": "permission_error",
      "importance": "primary",
      "annotation": "The role is not authorized to perform ecs:UpdateService."
    }
  ],
  "root_cause": {
    "summary": "The deployment IAM role lacks permission to update the ECS service.",
    "technical_explanation": "Authentication succeeded, but the AWS IAM policy did not allow ecs:UpdateService.",
    "confirmed": true
  },
  "recommendations": [
    {
      "step_number": 1,
      "type": "immediate_fix",
      "action": "Grant ecs:UpdateService to the deployment role.",
      "risk_level": "medium",
      "difficulty": "moderate"
    }
  ],
  "split": "train",
  "annotation": {
    "annotator_ids": ["annotator-01"],
    "review_status": "reviewed",
    "agreement_status": "agreed",
    "annotated_at": "2026-07-19T09:30:00+05:30"
  }
}
```

---

# 11. Artifact Types

Supported artifact types:

- pipeline_log
- job_log
- workflow_yaml
- terraform_file
- terraform_variables
- json_metadata
- dockerfile
- deployment_manifest
- archive

Rules:

- Every artifact must have a checksum.
- Raw and sanitized versions must be separated.
- Secrets must be masked before training or external AI use.
- Line numbering must remain stable after sanitization.
- Large binary files should not be placed directly in training manifests.

---

# 12. Directory Structure

```text
dataset/
├── README.md
├── DATASET_CARD.md
├── ANNOTATION_GUIDE.md
├── CHANGELOG.md
├── VERSION
├── licenses/
├── schemas/
│   ├── sample.schema.json
│   ├── annotation.schema.json
│   └── knowledge_chunk.schema.json
├── raw/
│   ├── github_actions/
│   ├── terraform/
│   ├── docker/
│   └── reproduced/
├── sanitized/
│   ├── github_actions/
│   ├── terraform/
│   ├── docker/
│   └── reproduced/
├── annotations/
│   ├── classification/
│   ├── evidence/
│   ├── root_cause/
│   └── recommendations/
├── manifests/
│   ├── samples.jsonl
│   ├── train.jsonl
│   ├── validation.jsonl
│   └── test.jsonl
├── knowledge_base/
│   ├── documents/
│   ├── chunks/
│   └── metadata/
├── quality_reports/
├── experiments/
└── scripts/
    ├── collect/
    ├── sanitize/
    ├── validate/
    ├── split/
    └── statistics/
```

---

# 13. Collection Workflow

```text
Identify Candidate Source
        ↓
Check License and Usage Basis
        ↓
Download or Reproduce Failure
        ↓
Assign Sample ID
        ↓
Store Raw Artifact
        ↓
Detect and Mask Secrets
        ↓
Normalize Format
        ↓
Annotate Category
        ↓
Annotate Evidence
        ↓
Write Root Cause
        ↓
Write Reference Recommendation
        ↓
Review Annotation
        ↓
Assign Dataset Split
        ↓
Run Quality Validation
```

---

# 14. Inclusion and Exclusion Criteria

Include a sample only when:

- The failure is genuine or intentionally reproduced.
- At least one relevant artifact is available.
- The category can be determined with reasonable confidence.
- The sample contains enough context for analysis.
- Sensitive information can be safely removed.
- Its use is legally and ethically acceptable.
- It is not a near-duplicate of an existing sample.

Reject a sample when:

- The log is incomplete beyond interpretation.
- The license or usage basis is unclear.
- Secrets cannot be safely removed.
- The root cause is entirely speculative.
- The artifact contains mostly unrelated output.
- It duplicates another sample with only formatting changes.

---

# 15. Annotation Process

Each sample should be annotated at four levels:

1. Classification
2. Evidence
3. Root cause
4. Recommendation

Recommended roles:

- Primary annotator
- Secondary annotator
- Reviewer or adjudicator

For an MSc project, the researcher may be the primary annotator, but an independently reviewed subset should still be included.

Recommended order:

```text
Read Full Artifact
    ↓
Identify Failed Stage
    ↓
Select Primary Category
    ↓
Select Secondary Category
    ↓
Mark Evidence Lines
    ↓
Write Root Cause
    ↓
Write Reference Fix
    ↓
Assign Confidence
    ↓
Submit for Review
```

---

# 16. Classification Rules

## Rule 1: Label the Root Failure

Example:

```text
Deployment failed because AWS returned AccessDenied.
```

Correct label:

```text
authorization_failure
```

Avoid using only:

```text
deployment_failure
```

## Rule 2: Use Deployment Failure When No More Specific Cause Exists

Example:

```text
Deployment rollout failed due to unhealthy service instances.
```

Use:

```text
deployment_failure
```

## Rule 3: Separate Authentication and Authorization

Authentication means identity could not be verified.

Authorization means identity was verified but lacked permission.

## Rule 4: Prefer Terraform-Specific Categories

A Terraform syntax error should be labeled:

```text
terraform_validation_failure
```

rather than the broader:

```text
configuration_failure
```

## Rule 5: Unknown Requires Review

`unknown_other` should require reviewer approval.

---

# 17. Evidence Annotation

## 17.1 Evidence Types

- error_message
- warning_message
- stack_trace
- failed_command
- exit_code
- permission_error
- authentication_error
- dependency_error
- network_error
- timeout_error
- syntax_error
- configuration_error
- terraform_resource_error
- deployment_status
- supporting_context

## 17.2 Evidence Importance

- primary
- supporting
- contextual

## 17.3 Span Rules

- Select the smallest span that preserves meaning.
- Include the exact error line.
- Include surrounding lines only when necessary.
- Do not select entire logs.
- Preserve exact line numbers.
- Do not include secrets.
- Mark multiple spans when multiple pieces of evidence are required.

Example:

```json
{
  "line_start": 443,
  "line_end": 445,
  "evidence_type": "permission_error",
  "importance": "primary",
  "annotation": "AWS denied the ECS update operation."
}
```

---

# 18. Root-Cause Annotation

A reference root cause should contain:

- Immediate cause
- Underlying cause
- Affected component
- Failed operation
- Relevant context

Good example:

```text
The GitHub Actions deployment role authenticated successfully but lacked
`ecs:UpdateService` permission for the target ECS service, causing the
production deployment step to fail.
```

Weak example:

```text
AWS error occurred.
```

Recommended structure:

```json
{
  "summary": "Short root cause",
  "technical_explanation": "Detailed explanation",
  "affected_component": "aws_ecs",
  "failed_operation": "ecs:UpdateService",
  "confirmed": true,
  "confidence": "high"
}
```

---

# 19. Recommendation Annotation

Each reference recommendation should include:

- Immediate action
- Verification step
- Prevention step
- Risk
- Difficulty

Example:

```json
[
  {
    "step_number": 1,
    "type": "immediate_fix",
    "action": "Add ecs:UpdateService permission to the deployment role.",
    "risk_level": "medium",
    "difficulty": "moderate"
  },
  {
    "step_number": 2,
    "type": "verification",
    "action": "Rerun the workflow and verify that the ECS service updates successfully.",
    "risk_level": "low",
    "difficulty": "easy"
  },
  {
    "step_number": 3,
    "type": "prevention",
    "action": "Add a pre-deployment IAM permission validation check.",
    "risk_level": "low",
    "difficulty": "moderate"
  }
]
```

---

# 20. Annotation Confidence

Annotators should assign:

- high
- medium
- low

High confidence means direct evidence and no meaningful alternative interpretation.

Medium confidence means strong evidence with some remaining uncertainty.

Low confidence means partial evidence, multiple plausible causes, or incomplete logs.

Low-confidence samples should be reviewed before inclusion in the test set.

---

# 21. Inter-Annotator Agreement

A reviewed subset should be independently annotated.

Recommended subset:

```text
10%–20% of samples
```

Recommended metrics:

- Cohen’s Kappa for category labels
- Span F1 or overlap for evidence
- Reviewer agreement for root-cause correctness
- Recommendation usefulness agreement

Suggested target:

```text
Cohen’s Kappa ≥ 0.75
```

This is a target, not a guaranteed threshold.

---

# 22. Dataset Size Targets

## Minimum Prototype

```text
500–800 total samples
```

## Stronger MSc Target

```text
1,000–2,000 total samples
```

## Per-Class Target

Minimum:

```text
75–100 samples per class
```

Preferred:

```text
150+ samples per class
```

## Evidence-Annotated Subset

```text
300–500 samples
```

## Root-Cause and Recommendation Evaluation Subset

```text
100–200 high-quality incidents
```

---

# 23. Class Balance

No single class should ideally represent more than approximately:

```text
20%–25% of the dataset
```

Possible imbalance treatments:

- Targeted data collection
- Stratified splitting
- Class weights
- Controlled augmentation
- Macro-averaged metrics

Oversampling must be applied only to the training set.

---

# 24. Train, Validation, and Test Split

Recommended split:

```text
70% training
15% validation
15% test
```

Alternative:

```text
80% training
10% validation
10% test
```

Requirements:

- Stratify by primary category.
- Keep related samples in the same split.
- Avoid repository leakage.
- Avoid duplicated logs across splits.
- Keep synthetic variations with their source sample.
- Keep reproduced variants in the same group.

---

# 25. Group-Aware Splitting

A normal random split can leak near-identical incidents.

Use `incident_group_id`, repository, workflow, or reproduction-template grouping.

Example group:

```text
Original failure
Synthetic variation 1
Synthetic variation 2
Reproduced version
```

All records in the group must remain in the same split.

---

# 26. Test Set Policy

The test set must:

- Remain unchanged after finalization.
- Contain no training duplicates.
- Include real public or reproduced failures.
- Avoid synthetic-data dominance.
- Include difficult and ambiguous cases.
- Represent multiple contexts where possible.

Suggested composition:

```text
70% real public samples
20% controlled reproduced samples
10% synthetic or adversarial samples
```

This may be adjusted based on availability, but realism should remain the priority.

---

# 27. Synthetic Data Policy

Allowed methods:

- Parameter substitution
- Path and identifier changes
- Controlled error-message variations
- Missing configuration values
- Permission substitutions
- Dependency version conflicts
- Noise insertion
- Log truncation experiments

Discouraged:

- Large volumes of unvalidated, fully LLM-generated logs
- Synthetic test-set dominance
- Generated root causes without expert review
- Examples that do not match actual tool behavior

Synthetic metadata:

```json
{
  "is_synthetic": true,
  "generation_method": "template_variation",
  "source_sample_id": "gha-000104",
  "validated_by": "annotator-01"
}
```

---

# 28. Negative and Ambiguous Samples

Include:

- Successful pipeline logs
- Warning-only logs
- Logs with no clear failure
- Multiple simultaneous failures
- Misleading final messages
- Partial logs
- Unknown provider formats

These samples support:

- False-positive reduction
- Unknown classification
- Confidence calibration
- Robustness testing

---

# 29. Secret Redaction

Secret types include:

- Passwords
- API keys
- Access tokens
- AWS keys
- GitHub tokens
- Private keys
- Database URLs
- JWTs
- Bearer tokens
- Connection strings

Redaction format:

```text
[REDACTED_PASSWORD]
[REDACTED_TOKEN]
[REDACTED_AWS_KEY]
[REDACTED_CONNECTION_STRING]
```

Redaction must preserve line structure.

Example:

```text
AWS_SECRET_ACCESS_KEY=[REDACTED_AWS_SECRET]
```

Audit metadata:

```json
{
  "secret_redaction": {
    "performed": true,
    "detected_count": 3,
    "types": ["token", "aws_secret"],
    "reviewed": true
  }
}
```

Original secret values must never be stored in manifests.

---

# 30. Data Normalization

Normalize dynamic values while preserving technical meaning.

Replace:

- Timestamps
- UUIDs
- Commit hashes
- IP addresses
- Temporary paths
- Account IDs
- Random ports
- Request IDs

Example:

```text
arn:aws:iam::123456789012:role/github-deploy
```

becomes:

```text
arn:aws:iam::[ACCOUNT_ID]:role/github-deploy
```

Do not replace:

- Error type
- Service name
- Failed operation
- Resource type
- Package name
- Relevant version number
- Exit code

---

# 31. Duplicate Detection

Use:

- SHA-256 checksum
- Normalized-text hash
- Similarity detection
- Repository and run metadata
- Error-signature comparison

Duplicate types:

- Exact duplicate
- Near duplicate
- Same incident with different formatting
- Synthetic variation
- Same log copied across multiple issues

Near duplicates should be grouped or removed.

---

# 32. Data Quality Checks

Every sample should pass automated validation.

Required checks:

- Valid JSON or JSONL structure
- Unique sample ID
- Existing artifact path
- Valid category
- Valid split
- Valid evidence line ranges
- No exposed secret patterns
- Non-empty sanitized content
- Root cause present where required
- Recommendation ordering valid
- Source metadata present
- Checksum present
- No train-test leakage

Quality status:

- valid
- needs_review
- rejected

---

# 33. Dataset Validation Script

Recommended command:

```bash
python scripts/validate_dataset.py \
  --manifest manifests/samples.jsonl \
  --schema schemas/sample.schema.json
```

Validation report should include:

- Total samples
- Valid and invalid samples
- Missing labels
- Duplicate samples
- Secret warnings
- Class distribution
- Split distribution
- Evidence coverage
- Leakage warnings

---

# 34. Dataset Versioning

Use semantic versioning.

Example:

```text
v1.0.0
```

Major version:

- Changed taxonomy
- Breaking schema change
- Removed or restructured samples

Minor version:

- Added samples
- Added metadata
- Added evidence annotations

Patch version:

- Corrected labels
- Fixed metadata
- Corrected typos

Required files:

```text
VERSION
CHANGELOG.md
DATASET_CARD.md
```

---

# 35. Dataset Card

The dataset card should include:

- Dataset name and version
- Purpose
- Sources
- License considerations
- Sample count
- Class distribution
- Split distribution
- Synthetic proportion
- Redaction process
- Annotation method
- Known limitations
- Ethical considerations
- Recommended uses
- Prohibited uses

---

# 36. Knowledge Base Dataset

The RAG knowledge base must be separated from the failure dataset.

Document schema:

```json
{
  "document_id": "aws-ecs-001",
  "provider": "aws",
  "product": "ecs",
  "title": "Amazon ECS API Permissions",
  "source_url": "https://docs.aws.amazon.com/...",
  "version": "2026-07",
  "license_or_terms": "official_documentation",
  "status": "active",
  "collected_at": "2026-07-19"
}
```

Chunk schema:

```json
{
  "chunk_id": "aws-ecs-001-017",
  "document_id": "aws-ecs-001",
  "heading": "UpdateService permissions",
  "content": "The caller must have permission to update the ECS service...",
  "chunk_index": 17,
  "token_count": 428,
  "tags": ["ecs", "iam", "authorization"]
}
```

---

# 37. Knowledge Base Quality Rules

- Prefer official documentation.
- Record source URL and collection date.
- Preserve headings and code blocks where practical.
- Avoid duplicate chunks.
- Mark outdated documents.
- Record version-specific content.
- Clearly distinguish official documentation from community content.

---

# 38. Retrieval Evaluation Dataset

Each retrieval test case should include:

```json
{
  "query_id": "query-001",
  "incident_sample_id": "gha-000104",
  "query_text": "AWS ECS UpdateService AccessDenied IAM deployment role",
  "relevant_chunk_ids": [
    "aws-ecs-001-017",
    "aws-iam-004-022"
  ],
  "relevance_grades": {
    "aws-ecs-001-017": 3,
    "aws-iam-004-022": 2
  }
}
```

Relevance scale:

- 3 = highly relevant
- 2 = relevant
- 1 = partially relevant
- 0 = not relevant

---

# 39. Evaluation Dataset Design

## Classification Set

Contains:

- Sanitized input
- Gold category
- Gold secondary label
- Group ID

## Evidence Set

Contains:

- Gold spans
- Evidence types
- Importance labels

## Reasoning Set

Contains:

- Gold root cause
- Accepted alternatives
- Required evidence IDs
- Unsupported claims that should not appear

## Recommendation Set

Contains:

- Gold remediation actions
- Verification requirements
- Prevention guidance
- Safety constraints

---

# 40. Human Evaluation Rubric

## Root-Cause Evaluation

| Criterion | Score |
|---|---|
| Correctness | 1–5 |
| Evidence grounding | 1–5 |
| Technical clarity | 1–5 |
| Completeness | 1–5 |
| Unsupported claims | 1–5 reversed |

## Recommendation Evaluation

| Criterion | Score |
|---|---|
| Technical correctness | 1–5 |
| Actionability | 1–5 |
| Safety | 1–5 |
| Relevance | 1–5 |
| Prevention quality | 1–5 |

---

# 41. Research Baselines

The dataset should support comparison of:

## Baseline A

Rules-only classification.

## Baseline B

TF-IDF with traditional machine learning.

## Baseline C

LLM without retrieval.

## Baseline D

LLM with retrieval.

## Proposed DevGuard AI Method

```text
Rules
+
Machine Learning
+
Evidence Extraction
+
RAG
+
LLM
+
Guardrails
```

The same fixed test set should be used across all baselines.

---

# 42. Metrics

## Classification

- Accuracy
- Macro precision
- Macro recall
- Macro F1
- Weighted F1
- Top-2 accuracy
- Top-3 accuracy
- Confusion matrix

## Evidence

- Precision
- Recall
- F1
- Line overlap
- Mean reciprocal rank

## Retrieval

- Precision@k
- Recall@k
- MRR
- nDCG

## Reasoning

- Correctness rating
- Evidence consistency
- Unsupported claim rate
- Explanation usefulness

## Recommendations

- Usefulness
- Actionability
- Safety
- Engineer acceptance rate

---

# 43. Bias Risks

Potential biases:

- Overrepresentation of GitHub Actions
- Overrepresentation of Terraform and AWS
- English-only logs
- Public repository bias
- Repeated common failure patterns
- Synthetic-data bias
- Annotator interpretation bias

Mitigations:

- Track source and provider distributions.
- Use macro metrics.
- Include difficult and rare cases.
- Label synthetic samples clearly.
- Document limitations.
- Use independent review where possible.

---

# 44. Ethical and Legal Requirements

The collection process must:

- Respect repository licenses and terms.
- Avoid private data without consent.
- Remove personal information.
- Remove credentials and tokens.
- Record source provenance.
- Document synthetic-data use.
- Follow institutional ethics requirements.

Any publicly released dataset should include only sanitized and legally shareable artifacts.

---

# 45. Data Retention

## Raw Public Data

Retain only when legally permitted.

## Raw Sensitive Data

Delete after successful sanitization and validation where appropriate.

## Sanitized Dataset

Retain for reproducibility.

## Annotation History

Retain with dataset versions.

## Rejected Samples

Store only minimal rejection metadata when sensitive content exists.

---

# 46. Recommended MVP Dataset Plan

## Phase 1 – Taxonomy and Schema

- Finalize 10–12 categories.
- Finalize JSON schema.
- Finalize evidence labels.
- Create annotation guide.

## Phase 2 – Initial Collection

Target:

```text
200–300 samples
```

Use public logs, controlled reproduction, and a limited synthetic subset.

## Phase 3 – Annotation Pilot

Annotate:

```text
50 samples
```

Evaluate:

- Label clarity
- Evidence rules
- Annotation time
- Disagreement rate

## Phase 4 – Main Collection

Expand to:

```text
800–1,200 samples
```

## Phase 5 – Review and Split

- Remove duplicates.
- Balance classes.
- Apply group-aware splitting.
- Freeze the test set.

## Phase 6 – Evidence and Reasoning Subsets

Create:

```text
300–500 evidence-annotated samples
100–200 root-cause and recommendation samples
```

---

# 47. Suggested Initial Distribution

For 1,200 samples across 12 categories:

| Category | Target |
|---|---:|
| build_failure | 100 |
| dependency_failure | 100 |
| test_failure | 100 |
| configuration_failure | 100 |
| authentication_failure | 100 |
| authorization_failure | 100 |
| network_failure | 100 |
| timeout_failure | 100 |
| terraform_validation_failure | 100 |
| terraform_plan_failure | 100 |
| terraform_apply_failure | 100 |
| deployment_failure | 100 |

Perfect equality is not required, but severe imbalance should be avoided.

---

# 48. Dataset Deliverables

The complete dataset package should include:

1. `DATASET_SPECIFICATION.md`
2. `DATASET_CARD.md`
3. `ANNOTATION_GUIDE.md`
4. `sample.schema.json`
5. `knowledge_chunk.schema.json`
6. `samples.jsonl`
7. `train.jsonl`
8. `validation.jsonl`
9. `test.jsonl`
10. Sanitized artifacts
11. Annotation files
12. Quality report
13. Class-distribution report
14. Leakage report
15. Dataset changelog

---

# 49. Example Sample

```text
Sample:
gha-000104

Source:
Public GitHub Actions failure

Primary Category:
authorization_failure

Secondary Category:
aws_iam_permission

Failure Stage:
deployment

Evidence:
AccessDenied: not authorized to perform ecs:UpdateService

Root Cause:
The GitHub Actions deployment role lacks permission to update the ECS service.

Recommendation:
Grant the required permission, verify resource scope, and rerun the workflow.

Split:
test
```

---

# 50. Final Dataset Architecture

```text
Public, Reproduced, and Synthetic Sources
        ↓
Raw Artifact Storage
        ↓
Secret Redaction
        ↓
Normalization
        ↓
Classification Annotation
        ↓
Evidence Annotation
        ↓
Root-Cause Annotation
        ↓
Recommendation Annotation
        ↓
Quality Review
        ↓
Group-Aware Train / Validation / Test Split
        ↓
Model Training and Evaluation
```

---

# 51. Architecture Decision

DevGuard AI will use a versioned, multi-task dataset architecture.

The dataset will:

- Support classification, evidence extraction, RAG, and LLM evaluation.
- Prioritize real public and controlled reproduced failures.
- Use synthetic data only as a controlled supplement.
- Preserve source provenance and licensing information.
- Apply secret redaction before training or external AI use.
- Use group-aware splits to prevent leakage.
- Maintain a fixed test set for fair baseline comparison.
- Record technical labels and human evaluation references.

This specification should be treated as the baseline before large-scale dataset collection begins.
