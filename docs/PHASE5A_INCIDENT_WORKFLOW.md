# Phase 5A — Incident Workflow

Primary product entity: **Incident**.

```text
Login → Dashboard / Projects
  → Create Project (if needed)
  → Create Incident wizard
      1. Details (project, title, severity, environment, source)
      2. Upload artifacts (.log/.txt/.json/.yml/…)
      3. Review → create incident → upload → start analysis
  → Analysis progress (polled stages)
  → Incident details
      Overview · Evidence · Sources · Recommendations
      Timeline · Notes · Files · Resolution · Report
  → Assign / status transitions (backend-enforced)
  → Resolve → Generate report → History / Notifications
```

`/diagnose` is not part of the end-user workflow; it redirects to `/incidents/new`.

AI pipeline (upload → mask → classify → retrieve → reason → persist) is unchanged and invoked via existing analysis APIs.
