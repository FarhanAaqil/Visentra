# Visentra forensic UI

React 19 + TypeScript + Vite front end for the Visentra assurance platform, in the
"Cherry Cinema" visual language: glass panels over an animated WebGL lattice that
shifts from cherry to amber to a crimson pulse as pipeline health degrades.

```bash
npm ci
npm run dev          # http://localhost:5173, talks to VITE_API_URL (default http://localhost:8000)
npm run lint         # oxlint, warnings are errors
npm run typecheck
npm run build
```

## Layout

| Path | What lives there |
|------|------------------|
| `src/lib/` | typed API client, live WebSocket feed, app store, formatting helpers |
| `src/ui/kit.tsx` | primitives: status pills, hash diff, ring gauges, bars, sheets, toasts |
| `src/scene/` | Three.js backdrop, lazy-loaded so it never blocks first paint |
| `src/views/` | lineage canvas, assurance report, audit trail |
| `src/panels/` | dataset inspector, interrogation room, signed inference, ingest drawer |

Deep links open a drill-down directly: `#model=<id>`, `#dataset=<id>`,
`#inference=<id>`, `#report`, `#audit`.
