# Phase 5A — Design System

Tokens live in `frontend/src/styles/tokens.css` and are the source of truth.

## Colour

| Token | Value |
|-------|-------|
| `--background` | `#0B1220` |
| `--surface` | `#111827` |
| `--surface-elevated` | `#1A2333` |
| `--primary` | `#2563EB` |
| `--secondary` | `#7C3AED` |
| `--success` / `--warning` / `--danger` / `--info` | `#10B981` / `#F59E0B` / `#EF4444` / `#06B6D4` |

Semantic incident status and severity mapping: `frontend/src/utils/statusMaps.ts`.

## Typography

Inter (loaded in `index.html`). Page title 32/700, section 22/600, card 18/600, body 15/400.

## Layout chrome

| Element | Size |
|---------|------|
| Sidebar expanded | 240px |
| Sidebar collapsed | 72px |
| Top bar | 72px |
| Button / input height | 44px (compact 36px) |
| Content max | ~1600px |

## Components

Reusable primitives under `frontend/src/components/ui/` (Button, Input, Select, Card, badges, DataTable, Modal, EmptyState, Skeleton, MetricCard, etc.) and shell under `components/layout/`.
