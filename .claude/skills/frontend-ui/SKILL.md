---
name: frontend-ui
description: Scaffold, extend, or restyle the Recipe Scraper Management UI (React + Vite, served static by Nginx). Use for building new UI panels/features, establishing frontend conventions, or polishing visual design of this project's React app.
---

# Recipe Scraper Management UI

Guidance for working on the project's frontend, as defined in
`Recipe Scraper Platform — Project.md` (Sections 2, 4, 7, 9).

## Tech stack (fixed by the project spec)

- **React + Vite**, built to static assets (`npm run build` → `ui/dist/`)
- No SSR, no Node server in production — Nginx serves the built static files
  and reverse-proxies `/api/` to the FastAPI backend on `127.0.0.1:8000`
- Lives at `/opt/recipe-platform/ui/` in the deployed app; `dist/` is the only
  build output Nginx cares about (see Section 9 nginx config)

## First-time scaffold

If `ui/` doesn't exist yet:

```bash
npm create vite@latest ui -- --template react-ts
cd ui
npm install
```

Recommended additions (server state + light data fetching, matching a
FastAPI JSON backend):
- `@tanstack/react-query` for server state (recipe list, scrape jobs, sites)
- A thin `src/api/client.ts` wrapping `fetch` against `/api/...` — one
  function per endpoint in Section 6 of the spec, not a generic passthrough
- Plain CSS or CSS modules by default; don't add a component library unless
  the user asks — this is an internal admin tool, not a product surface

Confirm with the user before adding a UI kit, CSS framework, or state
library beyond react-query — those are real decisions, not defaults to
silently assume.

## Feature → component mapping (spec Section 7)

Structure `src/features/` by the panels the spec calls out, not by generic
`components/`/`pages/` buckets:

```
src/
├── api/
│   └── client.ts
├── features/
│   ├── sites/          # Sites panel — add/remove/enable/disable targets
│   ├── scrape-queue/    # trigger scrapes, view job status/logs
│   ├── recipe-review/   # browse pending, approve/reject, edit before saving
│   ├── ingredients/     # inline ingredient editor
│   └── images/          # image preview alongside recipe data
├── App.tsx
└── main.tsx
```

Each feature folder owns its own components, hooks, and types — cross-feature
sharing goes through `src/api/` or a small `src/shared/` if a real duplication
shows up, not preemptively.

## Conventions

- Fetch calls always go through `src/api/client.ts`, never inline `fetch()`
  in components — the base path (`/api`) and error handling live in one place
- Use react-query for anything that hits the API; local `useState` for pure
  UI state (form drafts, open/closed panels)
- Recipe `status` (`pending | approved | rejected`) drives the review UI —
  treat it as the source of truth, don't invent parallel client-side state
- Match backend field names as-is (`prep_time`, `cook_time`, `image_path`,
  etc.) — don't relabel in the frontend layer

## Visual design / polish

For new layouts, mockups, or a visual pass before wiring up real data, use
the `design` skill to draft the screen first — it's faster to iterate on a
canvas than to reshuffle real components. Bring the result back here to
implement against the feature structure above.

If the UI needs charts/stats (e.g. scrape job history, site health), load
the `dataviz` skill before writing any chart code.

## Build & serve

```bash
npm run build        # outputs ui/dist/
```

Nginx serves `ui/dist/` directly (Section 9) — there is no dev-mode serving
in production. For local development, `npm run dev` against a running API
(`VITE_API_BASE` or a Vite proxy to `127.0.0.1:8000`) is fine; don't wire
that proxy into the production Nginx config.
