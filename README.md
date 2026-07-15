# Market Research

A UI app that conducts used market price and sales research and creates sale listing content for target online marketplaces (Facebook Marketplace, OfferUp, and others) for used items you enter.

## Features

- **Item identification** — Gather item details and photos, search for matches, and refine until the specific item is identified.
- **Market research** — Generate reports on used prices, demand, and optimal marketing angles.
- **Listing content** — Produce marketplace-ready titles and descriptions when you approve the research.

## Tech Stack

- **Python** with [uv](https://docs.astral.sh/uv/) for package management
- **FastAPI** for the API
- **LiteLLM** for inference across OpenAI and other model providers
- **Docker** and **docker-compose** for containerization

## Getting Started

### Backend

Requires Python 3.12+.

```bash
uv sync
uv run python main.py
# or equivalently:
uv run uvicorn app.main:app --reload --port 8000
```

`main.py` at the repo root is a thin convenience wrapper around `uvicorn.run("app.main:app", ...)`;
the real backend entry point is the `app` package (FastAPI app factory in `app/main.py`).

Copy `.env.example` to `.env` and set your API keys before running inference features.

Once running, check `GET /healthz` and the interactive docs at `/docs`.

### Frontend

Requires Node 24+ and [pnpm](https://pnpm.io/).

```bash
cd frontend
pnpm install
pnpm dev
```

The dev server (default `http://localhost:5173`) proxies `/api` and `/healthz` to the
backend (default `http://localhost:8000`; see `frontend/vite.config.js`).

### Docker Compose (both services together)

Requires Docker with the Compose plugin. Copy `.env.example` to `.env` first (the
`backend` service loads it via `env_file`).

```bash
docker compose up --build
```

This starts:

- `backend` — the FastAPI app, built from the root `Dockerfile`, on `http://localhost:8000`
- `frontend` — the Vite dev server (with HMR), built from `frontend/Dockerfile`'s `dev`
  stage, on `http://localhost:5173`, proxying to `backend` over the Compose network

For a "prod-like" local preview that serves the static `pnpm build` output (the same
`frontend/dist` artifact later deployed to Cloudflare Pages) via nginx instead of the Vite
dev server:

```bash
docker compose --profile prod up --build backend frontend-prod
# serves the built frontend at http://localhost:8080, with /api and /healthz
# reverse-proxied to the backend container (see frontend/nginx.conf)
```

Stop everything with `docker compose down` (add `--profile prod` if you started
`frontend-prod`).

## Backend Structure

- `app/main.py` — FastAPI app factory, CORS, `/healthz`, router registration
- `app/config.py` — pydantic-settings `Settings` read from `.env`
- `app/api/` — routers: `identify.py`, `research.py`, `listing.py`
- `app/services/` — `llm.py` (LiteLLM chat/vision), `search.py` (Tavily-backed search
  provider), `identification.py`, `research.py`, `listing.py`
- `app/schemas/` — pydantic request/response models per vertical
- `app/prompts/` — prompt templates per vertical
- `tests/` — pytest, with LLM/search calls mocked (no real network calls)

## Frontend Structure

See [frontend/README.md](frontend/README.md) for the Vite + React wizard UI
(`identify` → `research` → `listing`), its API client, and component breakdown.

## Containerization

- `Dockerfile` (repo root) — multi-stage, `uv`-based backend image. Builder stage runs
  `uv sync --frozen` (deps, then the project itself); runtime stage is a slim
  `python:3.12-slim` running as a non-root user via
  `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- `frontend/Dockerfile` — multi-stage frontend image with three targets: `base` (Node +
  pnpm via corepack), `dev` (runs `pnpm dev --host`, used by the `frontend` Compose
  service), and `prod` (builds `pnpm build` and serves `frontend/dist` — the same
  artifact that will later be deployed to Cloudflare Pages — via nginx, with
  `frontend/nginx.conf` reverse-proxying `/api` and `/healthz` to the `backend` Compose
  service; used by the optional `frontend-prod` Compose service).
- `docker-compose.yml` — `backend` (port 8000, `env_file: .env`) + `frontend` (port 5173,
  dev server) by default; `frontend-prod` (port 8080, nginx) behind the `prod` profile.
  See [Docker Compose](#docker-compose-both-services-together) above for usage.

## CI / Deployment

- `.github/workflows/ci.yml` — runs on every push/PR to any branch. Lints and type-checks
  and tests the backend (`ruff check`, `basedpyright`, `pytest`) and builds the frontend
  (`pnpm install && pnpm build`). Safe and non-deploying — no secrets used, nothing
  published.
- **All deploy workflows below are `workflow_dispatch` (manual) only. None of them have
  ever been run — nothing has been deployed anywhere.** Per the project plan: *DO NOT
  ACTUALLY DEPLOY YET.*
  - `.github/workflows/cloudflare_deploy.yml` — builds `frontend/dist` and publishes it to
    Cloudflare Pages via `cloudflare/pages-action`. Needs `CLOUDFLARE_API_TOKEN` /
    `CLOUDFLARE_ACCOUNT_ID` repo secrets (see `deploy/tf/`).
  - `.github/workflows/publish-backend-image.yml` — builds the root `Dockerfile` and
    pushes it to GHCR (`ghcr.io/<owner>/market-research-backend`). Actual hosting target
    for the backend container is deferred/undecided; this only builds and publishes the
    image.
- `deploy/tf/` — Terraform for the Cloudflare Pages project
  (`cloudflare_pages_project.market_research`, name kept identical to the
  `projectName` used in `cloudflare_deploy.yml`) plus `github_actions_secret` resources
  for `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`. No `.tfvars` are committed —
  supply `cloudflare_api_token`, `cloudflare_account_id`, `github_token`,
  `github_username`, `github_repo_name` yourself (e.g. via an untracked `.tfvars` file or
  `TF_VAR_*` env vars) when/if you actually run `terraform plan`/`apply`.

## API

- `GET /healthz`
- `POST /api/identify` — multipart form (`description`, `known_attributes` JSON string,
  `conversation` JSON string, optional `images` files) → candidates + `locked` flag
- `POST /api/research` — locked item JSON → `price_range` / `demand` / `marketing_angle` / `sources`
- `POST /api/listing` — item + approved research JSON → per-marketplace title/description
  (Facebook Marketplace, OfferUp); returns `400` if `research_approved` is not `true`

## Quality Checks

```bash
uv run pytest
uv run ruff check .
uv run basedpyright
```

## Development Status

Backend (identify/research/listing verticals on FastAPI + LiteLLM + Tavily) and frontend
(Vite + React wizard) are implemented and verified. Containerization (Docker +
docker-compose) and CI/deploy scaffolding (GitHub Actions + Terraform) are in place; see
[docs/plan.md](docs/plan.md) for the full project plan. Deploy workflows are manual-only
and have not been run — nothing is deployed yet.
