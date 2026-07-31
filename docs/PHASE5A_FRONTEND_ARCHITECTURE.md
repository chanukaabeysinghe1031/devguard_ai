# Phase 5A — Frontend Architecture

**Status:** Implemented (Module 5A.1–5A.5 core + supporting screens)  
**Stack:** React 18 · Vite 5 · TypeScript · React Router 6 · TanStack Query · Tailwind 3 · Zod · React Hook Form · Recharts · Lucide

## Layout

```text
frontend/src/
├── app/           # App, router, providers, queryClient, routeGuards
├── api/           # Typed /api/v1 clients + queryKeys
├── assets/        # Brand logo exports (Phase 5D)
├── components/
│   ├── brand/     # BrandLogo, BrandMark, BrandLoadingMark
│   ├── loading/   # Full-screen / auth / project loaders
│   ├── ui/        # Design-system primitives
│   └── layout/    # AppShell, Sidebar, TopBar, menus
├── features/      # (reserved; pages currently host feature UI)
├── hooks/         # useAuth, useProjectBootstrap, motion helpers
├── layouts/       # AuthLayout, AuthVisualPanel
├── pages/         # Route-level screens by domain
├── stores/        # UI preferences (sidebar collapse)
├── styles/        # tokens.css, brand-animations.css
├── types/         # API-aligned TypeScript models
└── utils/         # cn, formatters, statusMaps, executionModeLabels
```

## Branding (Phase 5D)

See `docs/PHASE5D_BRANDING_AND_LOADING_UX.md` for asset paths, auth transitions (`/auth/signing-in`, `/auth/creating-workspace`, `/auth/joining-organization`), and project bootstrap loading.
## Data flow

1. Session JWT + refresh token in `sessionStorage` (`devguard.session`)
2. `apiFetch` attaches Bearer + `X-Organization-Id`
3. On 401: single-flight `POST /auth/refresh`, then retry; else clear session → `/login?next=`
4. TanStack Query owns server state; mutations invalidate matching `queryKeys`
5. No production mock data in pages

## Auth & roles

- Frozen org roles only: `organization_owner`, `organization_admin`, `engineer`, `viewer`
- Admin nav/routes require owner/admin (platform admin via `platform_role` when present)
- `/diagnose` redirects to `/incidents/new`

## Styling

Single strategy: CSS variables in `styles/tokens.css` mapped through `tailwind.config.js`. Do not introduce a second theme system.
