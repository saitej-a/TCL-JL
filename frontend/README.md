# TCS Joining Tracker — Frontend

The SPA for the TCS Joining Tracker platform: Vite + React 18 + TypeScript
(strict) + Tailwind CSS v4, per Phase 9.1's decisions (`.planning/phases/TCS-JL-09.1-spa-foundation-and-api-client/09.1-CONTEXT.md`).

## Quick start

```bash
cd frontend
npm install
npm run dev
```

The dev server listens on **http://localhost:5173** (`strictPort` — the port is
part of the topology).

### The dev proxy (same-origin API)

The Vite dev server proxies these paths to the compose stack's nginx on :80
(which forwards to the Django `web` container):

| Path | Proxied to | Why |
|---|---|---|
| `/api` | `http://localhost:80` | All API traffic (`/api/v1/...`) |
| `/admin` | `http://localhost:80` | Django admin |
| `/static` | `http://localhost:80` | Static assets |
| `/media` | `http://localhost:80` | Uploaded media |

This keeps the SPA **same-origin** with the API in dev exactly as a reverse
proxy will in production — no CORS setting is touched anywhere in `config/`.
With `docker compose up -d` running, `http://localhost:5173/api/v1/...`
answers from the real backend.

### API base URL

`src/api/client.ts` reads `VITE_API_BASE_URL` (default `/api/v1`) — the only
module that touches this env var. In development you never need to set it; the
relative path flows through the proxy above.

## Commands

| Command | What it does |
|---|---|
| `npm run dev` | Dev server on :5173 with the API proxy |
| `npm run lint` | ESLint (typescript-eslint + react-hooks + react-refresh) |
| `npm run typecheck` | `tsc --noEmit` (strict; no `any` anywhere) |
| `npm run test:run` | Vitest + RTL, headless |
| `npm run test` | Vitest in watch mode |
| `npm run build` | `tsc -b && vite build` → `dist/` |
| `npm run preview` | Serve the production build locally |

Run them all (the phase gate): `npm run lint && npm run typecheck && npm run test:run && npm run build`.

## Design tokens

`src/index.css` is the token layer: the `@theme` block transcribes 05 §4.1's
palette (brand scale + semantic aliases) and the `.dark` override flips the
same custom properties. Component-facing constants (typography roles, surface
classes) live in `src/theme/tokens.ts`; category/status badge maps live in
`src/theme/badges.ts`. See **05_UI_UX_SPECIFICATION.md §4** for the source of
truth — components never invent hex values or spacing.

## Architecture notes

- **History-mode routing** (`createBrowserRouter`) is live from 9.1. Whatever
  serves `dist/` in production must rewrite unknown paths to `index.html`
  (nginx `try_files ... /index.html` or a Vercel rewrite) or deep links 404 —
  recorded as an open item (9.1 D4).
- **Token storage** follows 06 §3.3 Option 1: the access token is memory-only;
  the refresh token sits in `localStorage` under one namespaced key and is
  blacklisted server-side on logout. The 401 path is a single-flight refresh
  with one bounded replay (see `src/api/client.ts`).
