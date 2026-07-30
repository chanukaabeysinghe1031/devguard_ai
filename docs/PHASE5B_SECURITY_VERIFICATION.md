# Phase 5B — Security Verification

| Control | Status |
|---------|--------|
| HMAC-SHA256 raw-body signature | Covered by unit + API tests |
| Invalid/missing signature rejected | Pass |
| Duplicate `X-GitHub-Delivery` idempotent | Pass |
| Unique pipeline external_run_id | Migration 009 |
| Installation tokens not persisted | Design + App provider cache only |
| Private key / webhook secret not in API | Schemas omit secrets |
| Fake provider blocked in production | Config validation |
| ZIP path traversal / symlink / size limits | `test_github_log_extractor` |
| Setup state encrypted + bound | Fernet + user/org/project |
| Tenant isolation on connections | Org-scoped queries |
| Safe GitHub URL rendering in UI | `isSafeGitHubUrl` |

Residual: real GitHub App smoke against a public HTTPS webhook is **manual/optional** (documented in LOCAL_GITHUB_SETUP).
