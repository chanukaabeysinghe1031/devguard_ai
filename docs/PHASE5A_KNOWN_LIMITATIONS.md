# Phase 5A — Known Limitations

1. **Admin Models / Audit / Evaluation-admin** — explicitly deferred (no list/write APIs); UI states deferred, nav badge, no fake actions.
2. **Reports** — JSON snapshots only; PDF not faked.
3. **Notification channel preferences** — in-app defaults documented; no preference store API.
4. **Forgot password** — unsupported; not advertised.
5. **Local Docker frontend** — compose bind-mount uses Vite **dev** server for MSc iteration; AWS/static packaging is a deployment step.
6. **Evidence viewer** — structured list/excerpt/details (not full IDE multi-pane).
7. **Visual screenshot pack** — covers login/dashboard/projects/incidents/history/reports/notifications at 3 viewports; not every incident tab.
8. **axe serious colour-contrast** — residual on muted text within approved dark palette.
9. **Global search** — Cmd+K searches projects + incidents via live list APIs (not a dedicated `/search` endpoint).
10. **Tagging** — Phase 5A RC uses `v1.0.0-rc2` so prior `v1.0.0-rc1` (diagnosis shell) is preserved.
