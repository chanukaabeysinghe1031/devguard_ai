# Phase 5D — Branding, Auth Animations, and Project Loading UX

**Status:** Implemented  
**Scope:** Frontend presentation only (no backend API contract changes)

## Brand splash (`/welcome`)

Full-screen intro (~5s) before login/register (once per browser tab):

1. Symbol logo fades in
2. HTML title **DevGuard AI** animates in
3. Tagline **AI-Powered Incident Intelligence** animates in (correct spelling; not the typo in `logo2.png`)
4. Navigates to `next` (default `/register`)

Gated by `RequireBrandSplash` + `sessionStorage` key `devguard.splash.seen`.

## Assets (updated)

| Role | Source | Runtime |
|------|--------|---------|
| Complete stacked logo | `frontend/assets/logo2.png` | `src/assets/brand-logo-full.png` (bg removed) |
| Symbol | `frontend/assets/logo.png` | `src/assets/brand-logo-icon.png` (bg removed) |

Auth form header uses **symbol + HTML wordmark** (not the raster tagline) so spelling stays correct.
The right-hand auth visual panel no longer shows a brand image.

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
