# frontend

Vite + React wizard UI for the Market Research Assistant: identify an item,
research the market, and generate ready-to-post marketplace listings.

Styling uses the Tailwind CDN script in `index.html` (no PostCSS build step).

## Develop

```bash
pnpm install
pnpm dev
```

The dev server proxies `/api` and `/healthz` requests to
`http://localhost:8000`, where the FastAPI backend runs (see `vite.config.js`).

## Build

```bash
pnpm build
pnpm preview
```

## Structure

- `src/api.js` — fetch-based client for `/api/identify`, `/api/research`,
  `/api/listing`, and `/healthz`.
- `src/App.jsx` — top-level wizard state (`identify` -> `research` ->
  `listing`).
- `src/components/IdentifyStep.jsx` — description + photo upload, chat-style
  refinement loop until an item is locked.
- `src/components/ResearchStep.jsx` — market research report with price
  range, demand, marketing angle, and clickable sources.
- `src/components/ListingStep.jsx` — generated Facebook Marketplace and
  OfferUp listings with copy-to-clipboard.
