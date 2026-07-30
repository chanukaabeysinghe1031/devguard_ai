# Phase 5A — Known Limitations

1. **Admin Models / Audit / Evaluation-admin** pages are intentional stubs pending list APIs and audit writers.
2. **Reports** are JSON snapshots (view/download). PDF export is not faked.
3. **Global search** uses composed list queries from the command palette pattern where implemented; dedicated `/search` API deferred.
4. **Forgot password** is unsupported by backend — UI must not advertise it.
5. **Access token TTL** remains short; refresh is wired in the product client (sessionStorage refresh token).
6. **Evidence viewer** is structured but not a full VS Code-style multi-pane editor yet — list + excerpt + details.
7. **Recommendation grouping** (Immediate / Verification / Prevention) depends on backend `prevention_type` / risk fields when present.
8. **Notification preferences** are informational; per-user preference persistence deferred.
9. **Docker frontend image** must be rebuilt to pick up the new SPA; bind-mount/dev server may already hot-reload.
10. Full E2E Playwright product suite and visual screenshot pack remain Module 5A.10 work.
