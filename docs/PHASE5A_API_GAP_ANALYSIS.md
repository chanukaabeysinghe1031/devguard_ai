# Phase 5A — API Gap Analysis

## Closed in Phase 5A

| Capability | Endpoint(s) | Notes |
|------------|-------------|-------|
| Dashboard KPIs | `GET /dashboard/summary`, trend, severity, categories, recent, active-analyses, activity | Aggregates existing tables |
| Notifications | `GET/POST/DELETE /notifications*` | Writers on assign, resolve, analysis complete/fail |
| Reports | `POST /incidents/{id}/reports`, `GET /reports`, `GET /reports/{id}`, download | JSON snapshot; no fake PDF |
| History | `GET /history/incidents` | Thin historical search wrapper |
| Evaluation read | `GET /evaluation/latest-metrics` | Reads versioned `latest_metrics.json` |

## Still open / deferred

| Capability | Status | Reason |
|------------|--------|--------|
| Audit log list + writers | Deferred P2 | Table exists; full mutation writers incomplete |
| Admin model catalogue API | Deferred | `model_versions` table; no product CRUD |
| Global `/search` | Deferred | FE composes project/incident list `?search=` |
| Notification preference store | Deferred | In-app defaults only |
| Recommendation acceptance persistence UI | Partial | Domain fields exist; full review workflow later |
| PDF report binary | Deferred | Spec allows JSON/HTML; PDF only when real generator exists |
| Forgot password | Deferred | No backend support — link hidden |

## Migrations

**None required** for Phase 5A APIs — reused schema-ahead tables from migration `005` and existing incident domain.
