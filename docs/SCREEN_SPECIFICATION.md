# DevGuard AI — SCREEN_SPECIFICATION

**Version:** 1.0  
**Status:** Approved  
**Document Type:** Screen Specification  
**Project Type:** MSc Dissertation + Commercial SaaS Platform

**Scope:** Authentication, Global Layout, Dashboard, Projects, Notifications, Upload Wizard, AI Analysis Progress, Incident Details, Evidence Viewer, Recommendations & Resolution, Incident Reports, History, Settings, User Profile, Administration, Design System & Responsive Behaviour

---

# Table of Contents

## Part 1 — Authentication, Global Layout, Dashboard, Projects, Notifications
1. Design Principles
2. Global Layout
3. Login Screen
4. Dashboard
5. Projects
6. Notification Center
7. Navigation
8. UI Standards

## Part 2 — Upload Wizard, AI Analysis Progress, Incidents, Evidence, Recommendations
1. Upload Wizard
2. AI Analysis Progress
3. Incident Details
4. Evidence Viewer
5. AI Recommendations
6. Resolution Workflow
7. Common States

## Part 3 — Reports, History, Settings, Administration, Design System
1. Incident Reports
2. History
3. Settings
4. User Profile
5. Administration
6. Design System
7. Component Library
8. Responsive Behaviour
9. Accessibility
10. End of Specification

---

# Part 1 — Authentication, Global Layout, Dashboard, Projects, Notifications

# 1. Design Principles

The interface should feel like a modern DevOps platform similar to
GitHub, Azure DevOps and Datadog.

Goals:

-   Minimal clicks
-   Dark mode first
-   AI-first experience
-   Responsive layout
-   Fast access to incidents
-   Consistent design language

------------------------------------------------------------------------

# 2. Global Layout

``` text
+---------------------------------------------------------+
| Top Navigation                                           |
+----------+----------------------------------------------+
| Sidebar  | Main Content                                 |
|          |                                              |
|          |                                              |
|          |                                              |
+----------+----------------------------------------------+
```

## Sidebar

-   Dashboard
-   Projects
-   Incidents
-   History
-   Reports
-   Notifications
-   Settings

## Top Navigation

-   Search
-   Notification Bell
-   User Profile
-   Theme Toggle

------------------------------------------------------------------------

# 3. Login Screen

## Purpose

Authenticate the user securely.

## Components

-   DevGuard AI Logo
-   Welcome Text
-   Email
-   Password
-   Remember Me
-   Login Button
-   Forgot Password
-   Loading Indicator

## Validation

-   Email required
-   Password required
-   Invalid credentials message

## Success

Redirect to Dashboard.

------------------------------------------------------------------------

# 4. Dashboard

## Purpose

Provide a real-time overview of projects, deployments and incidents.

## Summary Cards

-   Open Incidents
-   Critical Incidents
-   Active Analyses
-   Successful Deployments
-   Failed Deployments
-   Average Resolution Time

## Charts

### Incident Trend

Line chart showing incidents over time.

### Severity Distribution

Pie chart:

-   Critical
-   High
-   Medium
-   Low

### Failure Categories

Bar chart:

-   Build
-   Deployment
-   Terraform
-   AWS
-   Configuration
-   Runtime

## Recent Incidents Table

Columns:

-   Incident ID
-   Project
-   Severity
-   Status
-   Detected Time
-   AI Confidence
-   Action

Clicking a row opens Incident Details.

## Quick Actions

-   New Analysis
-   Upload Logs
-   Create Project
-   Generate Report

------------------------------------------------------------------------

# 5. Projects

## Purpose

Manage monitored software projects.

## Project List

Columns

-   Name
-   Repository
-   Provider
-   Environment
-   Last Deployment
-   Open Incidents
-   Status

## Create Project Dialog

Fields

-   Project Name
-   Description
-   Repository URL
-   CI/CD Provider
-   Cloud Provider
-   Environment

Buttons

-   Save
-   Cancel

## Project Details

Display

-   Project Information
-   Deployment History
-   Open Incidents
-   Recent Analyses
-   Team Members (future)

Actions

-   Edit
-   Archive
-   Analyse Logs

------------------------------------------------------------------------

# 6. Notification Center

## Purpose

Display system alerts and AI notifications.

## Notification Types

-   Deployment Failed
-   Deployment Warning
-   Build Failed
-   Terraform Failed
-   AI Analysis Completed
-   Recommendation Ready

## Components

-   Notification List
-   Severity Badge
-   Timestamp
-   Mark Read
-   Mark All Read
-   Filter

## Filters

-   Unread
-   Critical
-   Warnings
-   Analysis
-   Reports

Selecting a notification opens the related incident.

------------------------------------------------------------------------

# 7. Navigation

## Sidebar Navigation

``` text
Dashboard
Projects
Incidents
History
Reports
Notifications
Settings
```

## Breadcrumb

Example

``` text
Dashboard
 >
Projects
 >
Customer Portal
 >
Incident INC-00045
```

------------------------------------------------------------------------

# 8. UI Standards

## Color Palette

Primary: Blue

Success: Green

Warning: Amber

Critical: Red

Background: Dark Gray

Cards: Slightly lighter gray

## Typography

Headings: Bold

Body: Regular

Code blocks: Monospace

## Buttons

Primary

-   Filled
-   Blue

Secondary

-   Outlined

Danger

-   Red

## Loading States

-   Skeleton cards
-   Progress bars
-   AI analysis animation

## Empty States

Examples

"No incidents found."

"No notifications available."

"No projects created yet."

## Error States

-   Network unavailable
-   Authentication expired
-   Server unavailable
-   AI analysis failed

Each error should provide a clear recovery action.

---

# Part 2 — Upload Wizard, AI Analysis Progress, Incidents, Evidence, Recommendations

# 1. Upload Wizard

## Purpose

Allow engineers to submit deployment artifacts for AI analysis.

## Steps

``` text
Step 1  Select Project
      ↓
Step 2  Upload Files
      ↓
Step 3  Review
      ↓
Step 4  Start AI Analysis
```

## Step 1 -- Project Selection

Fields

-   Project
-   Environment
-   CI/CD Provider
-   Cloud Provider

Buttons

-   Next
-   Cancel

------------------------------------------------------------------------

## Step 2 -- Upload Files

Supported files

-   GitHub Actions logs
-   Terraform files
-   Backend logs
-   Frontend logs
-   Configuration files
-   ZIP archives

Validation

-   File type
-   Maximum size
-   Duplicate detection
-   Malware scan (future)

------------------------------------------------------------------------

## Step 3 -- Review

Display

-   Uploaded files
-   Total size
-   Number of files
-   Selected project
-   Environment

Buttons

-   Back
-   Start Analysis

------------------------------------------------------------------------

# 2. AI Analysis Progress

## Purpose

Show analysis progress while backend services execute.

## Progress Pipeline

``` text
✔ Upload Complete
↓
✔ File Validation
↓
✔ Secret Masking
↓
✔ Log Cleaning
↓
✔ Metadata Extraction
↓
✔ Feature Extraction
↓
✔ Failure Classification
↓
✔ Evidence Extraction
↓
✔ Documentation Retrieval (RAG)
↓
✔ LLM Root Cause Analysis
↓
✔ Recommendation Generation
↓
✔ Incident Created
```

Each completed stage should show elapsed time.

Display:

-   Progress bar
-   Current stage
-   Estimated remaining time
-   Cancel button (before AI reasoning starts)

------------------------------------------------------------------------

# 3. Incident Details

## Purpose

Provide a complete view of a deployment incident.

## Header

Display

-   Incident ID
-   Title
-   Project
-   Repository
-   Provider
-   Environment
-   Severity
-   Status
-   Created Time
-   Assigned User

Actions

-   Generate Report
-   Mark Resolved
-   Reopen
-   Export

------------------------------------------------------------------------

## AI Summary Card

Contains

-   Executive summary
-   Confidence score
-   Estimated impact

------------------------------------------------------------------------

## Classification Card

Fields

-   Failure category
-   Confidence
-   Risk level
-   AI model version

------------------------------------------------------------------------

## Timeline

Display chronological events

-   Upload received
-   Analysis started
-   Classification completed
-   Recommendations generated
-   Resolution completed

------------------------------------------------------------------------

# 4. Evidence Viewer

## Purpose

Present supporting technical evidence.

## Evidence Table

Columns

-   Source File
-   Line Number
-   Evidence Type
-   Importance
-   Description

Clicking an item opens a side panel.

------------------------------------------------------------------------

## Side Panel

Display

-   Syntax-highlighted log snippet
-   Highlighted error
-   Explanation
-   Why AI selected this evidence

Evidence types

-   Stack Trace
-   Error Message
-   Terraform
-   YAML
-   Exception
-   Warning
-   Configuration

------------------------------------------------------------------------

## Related Documentation

Cards linking to

-   GitHub Actions
-   Terraform
-   AWS
-   Docker
-   Kubernetes

------------------------------------------------------------------------

# 5. AI Recommendations

## Purpose

Guide engineers through resolution.

Each recommendation contains

-   Step Number
-   Action
-   Explanation
-   Expected Result
-   Risk
-   Estimated Difficulty

Example

``` text
Step 1
Verify the IAM role attached to the deployment workflow.

Expected Result
The role contains ecs:UpdateService permission.

Risk
Low
```

------------------------------------------------------------------------

## Prevention Section

Display

-   Best practices
-   Suggested CI improvements
-   Security recommendations
-   Future prevention checklist

------------------------------------------------------------------------

# 6. Resolution Workflow

Engineer actions

-   Add Resolution Note
-   Mark In Progress
-   Mark Resolved
-   Reopen Incident

## Resolution Form

Fields

-   Resolution Summary
-   Notes
-   Root Cause Confirmed
-   Time Spent
-   Attach Supporting Files

Buttons

-   Save
-   Resolve Incident

After resolution

-   Generate Incident Report
-   Return to Dashboard
-   View History

------------------------------------------------------------------------

# 7. Common States

## Loading

-   Skeleton cards
-   Animated progress
-   Disabled actions during analysis

## Empty

Examples

-   No evidence found
-   No recommendations generated
-   No uploaded files

## Errors

-   Upload failed
-   AI analysis failed
-   Unsupported file
-   Network timeout
-   Report generation failed

Each error must include:

-   Clear explanation
-   Retry option
-   Contact support (future)

---

# Part 3 — Reports, History, Settings, Administration, Design System

# 1. Incident Reports

## Purpose

Allow engineers to generate professional reports for documentation,
audits and knowledge sharing.

## Report Formats

-   PDF
-   Markdown
-   JSON

## Report Contents

-   Incident Summary
-   Timeline
-   AI Summary
-   Failure Category
-   Confidence Score
-   Evidence
-   Root Cause
-   Resolution Steps
-   Preventive Actions
-   Resolution Notes
-   Engineer
-   Resolution Time

## Actions

-   Preview
-   Download
-   Regenerate
-   Share (future)

------------------------------------------------------------------------

# 2. History

## Purpose

Browse every previous AI analysis.

## Filters

-   Project
-   Repository
-   Provider
-   Severity
-   Status
-   Category
-   Date Range
-   Assigned User

## History Table

Columns

-   Incident ID
-   Project
-   Category
-   Severity
-   Status
-   Created
-   Resolved
-   AI Confidence

## Actions

-   View
-   Reopen
-   Generate Report
-   Export

------------------------------------------------------------------------

# 3. Settings

## Sections

### General

-   Theme
-   Language
-   Time Zone

### Notifications

-   In-App
-   Email (future)
-   Slack (future)
-   Microsoft Teams (future)

### AI Settings

-   Preferred LLM
-   Confidence Threshold
-   Enable Debug Logs

### Security

-   Change Password
-   Two-Factor Authentication (future)
-   Active Sessions

------------------------------------------------------------------------

# 4. User Profile

Display

-   Avatar
-   Name
-   Email
-   Role
-   Organization
-   Last Login

Actions

-   Edit Profile
-   Change Password
-   Sign Out

------------------------------------------------------------------------

# 5. Administration

## Users

-   Create User
-   Disable User
-   Assign Roles

## Projects

-   Archive
-   Delete
-   Ownership Transfer

## AI Models

Display

-   Model Name
-   Version
-   Training Date
-   Status

## Audit Log

Track

-   Login
-   Incident Changes
-   Report Generation
-   Configuration Changes

------------------------------------------------------------------------

# 6. Design System

## Color Palette

Primary: Blue

Success: Green

Warning: Amber

Critical: Red

Background: #111827

Surface: #1F2937

Border: #374151

## Typography

-   H1
-   H2
-   H3
-   Body
-   Caption
-   Monospace for logs

## Icons

-   Incident
-   Warning
-   Success
-   Upload
-   Report
-   History
-   Settings

------------------------------------------------------------------------

# 7. Component Library

Reusable Components

## Layout

-   Sidebar
-   Top Navigation
-   Breadcrumb
-   Footer

## Cards

-   Summary Card
-   Incident Card
-   Recommendation Card
-   Evidence Card

## Tables

-   Incident Table
-   History Table
-   Evidence Table
-   Notification Table

## Forms

-   Login Form
-   Upload Form
-   Project Form
-   Resolution Form

## Feedback

-   Toast
-   Alert
-   Confirmation Dialog
-   Progress Indicator
-   Skeleton Loader

## Charts

-   Line Chart
-   Bar Chart
-   Pie Chart
-   Area Chart

------------------------------------------------------------------------

# 8. Responsive Behaviour

## Desktop

-   Full sidebar
-   Multi-column layout
-   Split evidence viewer

## Tablet

-   Collapsible sidebar
-   Responsive cards
-   Stacked charts

## Mobile

-   Bottom navigation
-   Single-column layout
-   Full-screen dialogs
-   Simplified tables

------------------------------------------------------------------------

# 9. Accessibility

Requirements

-   WCAG AA target
-   Keyboard navigation
-   Visible focus indicators
-   Screen-reader labels
-   High-contrast support
-   Semantic HTML
-   Accessible form validation

------------------------------------------------------------------------

# 10. End of Specification

## Complete Screen List

-   Login
-   Dashboard
-   Projects
-   Upload Wizard
-   AI Analysis Progress
-   Incident Details
-   Evidence Viewer
-   Recommendations
-   Resolution
-   Reports
-   History
-   Notifications
-   Settings
-   User Profile
-   Administration

------------------------------------------------------------------------

## UI Design Goals

The interface should:

-   Minimize investigation time.
-   Present AI explanations clearly.
-   Make incidents the primary navigation object.
-   Keep technical details available without overwhelming users.
-   Scale from the MSc MVP to a commercial SaaS platform with minimal
    redesign.
