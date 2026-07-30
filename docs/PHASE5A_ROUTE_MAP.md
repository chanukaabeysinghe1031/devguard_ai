# Phase 5A — Route Map

| Path | Auth | Screen | Data |
|------|------|--------|------|
| `/login` | Public | Login | `POST /auth/login` |
| `/register` | Public | Register | `POST /auth/register` |
| `/` | Protected | → `/dashboard` | — |
| `/dashboard` | Protected | Command centre | `/dashboard/*` |
| `/projects` | Protected | Project list | `GET /projects` |
| `/projects/new` | Writer UI | Create wizard | `POST /projects` |
| `/projects/:id` | Protected | Project detail | project + incidents + runs |
| `/projects/:id/edit` | Writer UI | Edit | `PATCH /projects/{id}` |
| `/pipeline-runs/:id` | Protected | Run detail | `GET /pipeline-runs/{id}` |
| `/incidents` | Protected | Incident list | `GET /incidents` |
| `/incidents/new` | Writer UI | Create + upload + analyse | incidents/files/analyses |
| `/incidents/:id` | Protected | Detail tabs | incident + analysis artifacts |
| `/incidents/:id/analysis` | Protected | Progress | `GET /analyses/{id}/status` |
| `/history` | Protected | History | `GET /history/incidents` |
| `/reports` | Protected | Report library | `GET /reports` |
| `/reports/:id` | Protected | Report detail | `GET /reports/{id}` |
| `/notifications` | Protected | Notification centre | `GET /notifications` |
| `/evaluation` | Protected | Research metrics | `GET /evaluation/latest-metrics` |
| `/settings/*` | Protected | Org/security/notifications | auth + org APIs |
| `/profile` | Protected | Profile | `/auth/me` + assigned incidents |
| `/admin/users` | Admin | Members | org members API |
| `/admin/system-health` | Admin | Health | `/health` `/health/ready` |
| `/admin/models` | Admin | Stub | pending model list API |
| `/admin/audit` | Admin | Stub | pending audit list API |
| `/admin/evaluation` | Admin | Stub | research CLI remains primary |
| `/diagnose` | Protected | **Redirect** | → `/incidents/new` |
| `/403` | Protected | Forbidden | — |
| `*` | Protected | 404 | — |
