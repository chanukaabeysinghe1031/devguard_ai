DevGuard AI
Customer Experience & Incident Workflow Specification

Version: 1.0

Status: Approved

Purpose:
Define the complete customer journey, user experience, incident lifecycle, AI workflow, and expected system behaviour from the moment a deployment issue occurs until the incident is resolved.

Table of Contents
Product Vision
Target Users
Customer Journey
Incident Lifecycle
User Workflow
Dashboard Experience
Incident Experience
AI Analysis Experience
Resolution Experience
Report Generation
Notification Experience
History Experience
Future Automated Workflow
MVP Scope
Customer Success Criteria
1. Product Vision

DevGuard AI is not just a log analyser.

It acts as an AI DevOps Engineer that continuously assists software engineers in understanding, diagnosing, documenting, and resolving CI/CD failures.

Instead of asking:

"Why did my deployment fail?"

The engineer should simply open DevGuard AI and immediately understand:

What happened
Why it happened
Where it happened
How to fix it
How to prevent it
2. Target Users

Primary users

Software Engineers
DevOps Engineers
Site Reliability Engineers
Cloud Engineers
Platform Engineers

Secondary users

Engineering Managers
Technical Leads
QA Engineers
3. Customer Journey
Step 1

Pipeline executes

↓

GitHub Actions

Terraform

Backend Deployment

Frontend Deployment

Step 2

Deployment fails

Examples

Build failure
Test failure
Deployment failure
Terraform failure
Docker failure
AWS permission error
Configuration error
Runtime exception
Step 3

Customer receives notification

Example

Production Deployment Failed

Repository:
customer-portal

Workflow:
deploy-production.yml

Severity:
Critical

Status:
AI Analysis Started
Step 4

Customer opens DevGuard AI

Dashboard immediately displays

Open incidents
Critical incidents
Recent failures
Active analyses
Step 5

Customer opens incident

AI begins explaining the problem.

Step 6

Customer reviews

AI Summary
Root Cause
Evidence
Documentation
Recommendations
Step 7

Customer fixes deployment

Step 8

Customer marks incident resolved

Step 9

Incident report generated

Step 10

Incident stored permanently

4. Incident Lifecycle
Detected
      │
      ▼
Analysing
      │
      ▼
Open
      │
      ▼
In Progress
      │
      ▼
Resolved
      │
      ▼
Closed

Optional states

Reopened
False Positive
Ignored
Analysis Failed
5. User Workflow
Login

↓

Dashboard

↓

Projects

↓

Pipeline Runs

↓

Incident

↓

AI Analysis

↓

Evidence

↓

Recommendations

↓

Incident Report

↓

History

6. Dashboard Experience

Dashboard should feel like a DevOps command centre.

Summary Cards

Open Incidents

Critical Incidents

Resolved Today

Average Resolution Time

Successful Deployments

Failed Deployments

Recent AI Analyses

Charts

Deployment success rate

Failure categories

Incident trend

Resolution time

Severity distribution

Recent Incidents
Production Deployment Failed

Critical

Open

5 minutes ago
7. Incident Experience

Every incident becomes the central object in the application.

Incident Header
Incident ID

Project

Repository

Environment

Pipeline

Workflow

Status

Severity

Detected Time

Assigned User
AI Summary

Example

Deployment failed because
the GitHub Actions runner
does not have permission
to update the ECS service.
Failure Classification

Category

Confidence

Risk

Technical Evidence

Evidence should show

Log file

Line number

Highlighted text

Importance

Explanation

Root Cause

Natural language explanation

Technical explanation

Related Documentation

GitHub Actions

Terraform

AWS

Docker

Official documentation

Recommendations

Step-by-step remediation

Expected result

Risk level

Estimated difficulty

Prevention

How to avoid this issue again

8. AI Analysis Experience

Pipeline

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

Feature Extraction

↓

Classification

↓

Evidence Extraction

↓

RAG

↓

LLM Reasoning

↓

Recommendation

↓

Database

↓

Frontend

Customer should only see

AI Analysis

█████████

Analysing logs...

Extracting evidence...

Finding documentation...

Generating recommendations...
9. Resolution Experience

Engineer performs fixes.

Examples

Update IAM Policy

Run terraform apply

Restart deployment

Re-run GitHub Actions

User can then

Mark Resolved

Add Notes

Reopen Incident

10. Incident Report

Customer can generate

PDF

Markdown

JSON

Report includes

Incident Summary

Timeline

Failure Category

AI Confidence

Evidence

Root Cause

Resolution Steps

Prevention

Resolution Notes

Engineer

Resolution Time

11. Notification Experience

MVP

Inside application

Notification bell

Dashboard alerts

Future

Email

Slack

Microsoft Teams

Discord

GitHub Checks

Notification Types

Deployment Failed

Deployment Warning

Security Issue

Terraform Failure

Build Failure

Test Failure

Recommendation Ready

Incident Reopened

12. History Experience

Every incident is searchable.

Filters

Project

Repository

Environment

Severity

Status

Failure Category

Date

Provider

Search

Sort

Export

13. Future Automated Workflow

Current MVP

User uploads logs

↓

AI Analysis

↓

Incident Created

Commercial Version

GitHub Webhook

↓

Pipeline Failed

↓

Logs Downloaded Automatically

↓

Incident Created

↓

AI Analysis

↓

Slack Notification

↓

Engineer Opens Dashboard
14. MVP Scope

The MSc implementation includes

✅ Authentication

✅ Project Management

✅ Manual Upload

✅ GitHub Actions Logs

✅ Terraform Files

✅ AI Failure Classification

✅ Evidence Extraction

✅ RAG Documentation

✅ Root Cause Analysis

✅ Step-by-Step Recommendations

✅ Incident Management

✅ Incident History

✅ Incident Reports

✅ In-App Notifications

Future versions

GitLab

Jenkins

Azure DevOps

Docker Analysis

Kubernetes

Slack

Email

Microsoft Teams

Predictive Analysis

Self-Healing Pipelines

15. Customer Success Criteria

The product is considered successful when a software engineer can:

✓ Identify a failed deployment within seconds

✓ Understand the root cause without manually searching logs

✓ View supporting evidence

✓ Receive accurate AI-generated remediation steps

✓ Generate an incident report

✓ Track incidents from creation to resolution

✓ Review historical incidents for future learning

✓ Extend the platform to additional CI/CD providers without redesigning the customer experience