# Phase 5B — API Contract

Public (HMAC):

| Method | Path |
|--------|------|
| POST | `/api/v1/integrations/github/webhook` |

Authenticated (JWT + org):

| Method | Path |
|--------|------|
| GET | `/integrations/github/status` |
| POST | `/integrations/github/install-url` |
| POST | `/integrations/github/setup` |
| GET | `/integrations/github/installations` |
| GET | `/integrations/github/installations/{id}/repositories` |
| GET | `/projects/{id}/integrations` |
| GET/POST/PATCH | `/projects/{id}/integrations/github` |
| POST | `/projects/{id}/integrations/github/test\|pause\|resume` |
| DELETE | `/projects/{id}/integrations/github` |
| GET | `/projects/{id}/integrations/github/workflows` |
| GET | `/projects/{id}/integrations/github/activity` |

See regenerated `docs/openapi.json` after Module 5B.8.
