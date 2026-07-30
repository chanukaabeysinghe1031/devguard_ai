# Phase 5A — Stub Closure

**Module:** 5A.10

## Inventory

| Item | Classification | Action |
|------|----------------|--------|
| Admin Models empty page | Admin-only future scope | Explicit deferred UI; no write buttons; nav badge “Deferred” |
| Admin Audit empty page | Admin-only future scope | Same |
| Admin Evaluation empty page | Admin-only future scope | Redirect copy to research `/evaluation`; deferred admin controls |
| Notification preferences | Acceptable documented limitation | Read-only explainer of in-app behaviour; no fake toggles |
| Form `placeholder=` attributes | Safe UX | Keep |
| Vitest / Playwright mocks | Safe test-only fixture | Keep in tests only |
| Legacy `DiagnosisPage` / `HomePage` | Must fix | Deleted (unrouted orphans) |
| Missing ErrorBoundary | Must fix | Added |
| Missing skip-to-content | Must fix | Added |
| UserMenu missing aria-label | Must fix | Added |
| Global Cmd+K search | Must fix (spec) | Command palette using live project/incident search APIs |
| TODO/FIXME in `src/` | None found | — |

## MVP decisions

| Capability | Read API exists? | Write required for MSc MVP? | Outcome |
|------------|------------------|-----------------------------|---------|
| Model registry UI | No | No | Deferred page, no actions |
| Audit log UI | No | No (research MVP) | Deferred page, no actions |
| Admin evaluation controls | Partial metrics via `/evaluation` | No | Deferred admin; user Evaluation remains |
| Notification channel prefs | No | No | Document in-app defaults only |

## Misleading UI removed

- Stub pages no longer say “coming soon” as if shipping imminently; they state **Deferred — not in MSc MVP**.
- Settings notification page has no disabled toggles pretending to save.
- Orphan diagnose/home pages removed so they cannot be revived without routes.
