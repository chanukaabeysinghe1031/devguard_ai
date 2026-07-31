# Phase 5D — Branding, Auth Animations, and Project Loading UX

**Status:** Implemented  
**Scope:** Frontend presentation only (no backend API contract changes)

## Asset audit

| Role | Original path | Format | Dimensions | Notes |
|------|---------------|--------|------------|-------|
| Complete logo (wordmark + tagline) | `frontend/assets/banner.png` | PNG RGB | 1983×793 | Fixed dark navy plate |
| Symbol-only logo | `frontend/assets/logo.png` | PNG RGBA | 1536×1024 | Dark plate; framed in UI |

Runtime imports use optimized copies (originals preserved):

| Alias | Path | Approx size |
|-------|------|-------------|
| `brandLogoFull` | `frontend/src/assets/brand-logo-full.png` | 800×320 |
| `brandLogoIcon` | `frontend/src/assets/brand-logo-icon.png` | 256×170 |

Favicon / PWA icons derived from the symbol:

- `frontend/public/favicon-16x16.png`
- `frontend/public/favicon-32x32.png`
- `frontend/public/favicon.png`
- `frontend/public/icons/icon-48x48.png`
- `frontend/public/icons/icon-192x192.png`
- `frontend/public/icons/icon-512x512.png`
- `frontend/public/site.webmanifest`

Export module: `frontend/src/assets/index.ts`

## Where each mark is used

**Complete logo (`BrandLogo variant="full"`):**

- Login, register, invitation accept (`AuthLayout` header)
- Project bootstrap loader wordmark (optional top)

**Symbol (`BrandMark` / `BrandLoadingMark`):**

- Expanded + collapsed sidebar
- Mobile navigation drawer
- Auth ambient visual panel
- Sign-in / workspace / join transitions
- Project bootstrap loader center mark
- Role-guard inline spinner
- Favicon + manifest icons

Product identity Lucide `ShieldCheck` marks in chrome were replaced. Semantic security icons in content pages (e.g. audit empty states) were left unchanged.

## Reusable components

| Component | Path |
|-----------|------|
| `BrandLogo` | `src/components/brand/BrandLogo.tsx` |
| `BrandMark` | `src/components/brand/BrandMark.tsx` |
| `BrandLoadingMark` | `src/components/brand/BrandLoadingMark.tsx` |
| `FullScreenBrandLoader` | `src/components/loading/FullScreenBrandLoader.tsx` |
| `AuthTransitionLoader` | `src/components/loading/AuthTransitionLoader.tsx` |
| `ProjectBootstrapLoader` | `src/components/loading/ProjectBootstrapLoader.tsx` |
| `InlineBrandSpinner` | `src/components/loading/InlineBrandSpinner.tsx` |

Motion primitives: `src/styles/brand-animations.css` (CSS keyframes only — no Framer Motion).

## Auth transition architecture

| Route | Trigger | Exit |
|-------|---------|------|
| `/auth/signing-in?next=` | Login API success | `/auth/me` ready + min ~750ms → `next` or `/dashboard` |
| `/auth/creating-workspace` | Register + auto-login success | User bootstrap + min ~900ms → `/dashboard` |
| `/auth/joining-organization?org=` | Invitation accept (hard nav hydrates session) | User bootstrap + min ~800ms → `/dashboard` |

Rules:

- Progress stages map to real frontend steps (session present, `/me` loaded), not fake percentages.
- 20s timeout → error + Retry / Return to sign in.
- `prefers-reduced-motion` collapsed via global `index.css` rules.

## Project loading architecture

Hook: `useProjectBootstrap(projectId)`

Real queries:

1. Project details (`GET /projects/:id`) — also implies access
2. Incident overview (`listIncidents` page 1)
3. Project integrations (soft-fail)
4. “Preparing AI analysis context” completes when project + incidents are ready

Full-screen loader only on cold entry (no cached project). Tab switches and background refetches use existing skeletons/tables.

## Animation rules

- Float ~6s, glow pulse ~3.5s, orbit ring ~1.35s, form enter ~360ms
- No video, no heavy canvas, no flashing
- Reduced motion: durations forced near-zero by global CSS

## Error handling

All full-screen loaders eventually complete, show an error with Retry, or redirect. Invitation and register flows prevent double submit via `isSubmitting` / button `isLoading`.

## Deferred items

- Dedicated forgot/reset password pages (not present in the product; no invented routes)
- Separate PageSkeleton redesign (existing `Skeleton` retained for page-level refresh)
- Visual screenshot pack under `frontend/reports/phase5d/screenshots/` (capture via Playwright visual suite when services are up)

## Testing evidence

- Unit: `src/components/brand/BrandLogo.test.tsx` (14 frontend unit tests total passing)
- E2E: `e2e/branding.spec.ts` (4/4 passing against live stack)
- Existing auth helpers updated for workspace registration fields + transition URLs

## Screenshots produced

Captured under `frontend/reports/phase5d/screenshots/`:

- `login-desktop.png`
- `login-mobile.png`
- `register-desktop.png`

## Quality gates (run locally)

```bash
cd frontend
npm run lint
npm test
npm run build
npm run test:e2e -- e2e/branding.spec.ts
```
