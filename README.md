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
  stage, on `http://localhost:5173`, proxying `/api` and `/healthz` to `backend` over the
  Compose network via `BACKEND_PROXY_TARGET` (server-only; not a `VITE_*` var, so it is
  never baked into the browser bundle)

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
  and tests the backend (`ruff check`, `basedpyright`, `pytest`) and the frontend
  (`pnpm test && pnpm build`). Safe and non-deploying — no secrets used, nothing
  published.
- **All deploy workflows below are `workflow_dispatch` (manual) only. None of them have
  ever been run — nothing has been deployed anywhere.** Per the project plan: *DO NOT
  ACTUALLY DEPLOY YET.*
  - `.github/workflows/cloudflare_deploy.yml` — builds `frontend/dist` and publishes it to
    Cloudflare Pages via `cloudflare/pages-action`. Needs `CLOUDFLARE_API_TOKEN` /
    `CLOUDFLARE_ACCOUNT_ID` repo secrets (see `deploy/tf/`). The build step now sets
    `VITE_BACKEND_URL` (from the `VITE_BACKEND_URL` Actions variable) so the built bundle
    calls the deployed Cloud Run backend directly instead of a relative path.
  - `.github/workflows/google-cloudrun-deploy.yml` — **new.** Builds the root `Dockerfile`,
    pushes a SHA-tagged image to Artifact Registry
    (`us-central1-docker.pkg.dev/<project>/market-research/market-research-backend:<sha>`),
    and deploys it to the `market-research-backend` Cloud Run service in `us-central1`.
    Free-tier-friendly and scale-to-zero (`min_instance_count = 0`). Auth is via a Service
    Account key JSON (`secrets.GCP_SA_KEY`), not Workload Identity Federation.
  - `.github/workflows/publish-backend-image.yml` — **superseded/dormant.** Backend hosting
    now targets Cloud Run (above), which pulls from Artifact Registry, not GHCR. This
    workflow still builds/pushes to GHCR
    (`ghcr.io/<owner>/market-research-backend`) if manually triggered, but is kept only for
    reference/fallback.
- `deploy/tf/` — Terraform for both the Cloudflare Pages project and the GCP Cloud Run
  backend, in one state:
  - Cloudflare: `cloudflare_pages_project.market_research` (name kept identical to the
    `projectName` used in `cloudflare_deploy.yml`) plus `github_actions_secret` resources
    for `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`.
  - GCP (`deploy/tf/gcp.tf`): an Artifact Registry Docker repo (`market-research`, in
    `us-central1`); a deploy service account (`market-research-deploy`, with a JSON key)
    used by CI; a runtime service account (`market-research-runtime`) that the Cloud Run
    service runs as; Secret Manager secret *containers* for `LLM_API_KEY`,
    `VISION_API_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `ZAI_API_KEY` (values are **not**
    set by Terraform — see below); the `market-research-backend` Cloud Run service itself
    (scale-to-zero, public via `allUsers` invoker); and `github_actions_secret.gcp_sa_key`
    (`GCP_SA_KEY`) + `github_actions_variable.vite_backend_url` (`VITE_BACKEND_URL`,
    populated from the Cloud Run service's URL) pushed straight into GitHub Actions.
  - No `.tfvars` are committed — supply `cloudflare_api_token`, `cloudflare_account_id`,
    `github_token`, `github_username`, `github_repo_name`, `gcp_project_id` (and optionally
    `gcp_region` / `frontend_origin`, which default to `us-central1` /
    `https://market-research.pages.dev`) yourself (e.g. via an untracked `.tfvars` file or
    `TF_VAR_*` env vars) when/if you actually run `terraform plan`/`apply`.

### Populating Cloud Run secrets

Terraform only creates the Secret Manager secret *containers* — it deliberately never
writes secret values, so they never enter tfstate or git. After `terraform apply`, add each
value out-of-band:

```bash
gcloud secrets versions add LLM_API_KEY --project=<PROJECT_ID> --data-file=-
gcloud secrets versions add VISION_API_KEY --project=<PROJECT_ID> --data-file=-
gcloud secrets versions add OPENAI_API_KEY --project=<PROJECT_ID> --data-file=-
gcloud secrets versions add TAVILY_API_KEY --project=<PROJECT_ID> --data-file=-
gcloud secrets versions add ZAI_API_KEY --project=<PROJECT_ID> --data-file=-
```

Each command reads the secret value from stdin (pipe it in, or type it and press
Ctrl-D) — only set the ones your provider configuration actually needs.

### Required GitHub Actions configuration

| Name | Kind | Set by |
| --- | --- | --- |
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | secret | Terraform (`deploy/tf/main.tf`) |
| `GCP_SA_KEY` | secret | Terraform (`deploy/tf/gcp.tf`) |
| `VITE_BACKEND_URL` | variable | Terraform (`deploy/tf/gcp.tf`, from the Cloud Run URL) |
| `GCP_PROJECT_ID` | variable | Terraform (`deploy/tf/gcp.tf`, mirrors the `gcp_project_id` input variable) |

## Model & provider configuration

Inference is configured per role in `.env`: a **chat** model (market research +
listing) and a **vision** model (item identification). Model IDs are
LiteLLM-style provider-prefixed; for any OpenAI-compatible endpoint use
`openai/<model>` together with `LLM_API_BASE`.

- `LLM_MODEL` / `LLM_API_BASE` / `LLM_API_KEY` — chat.
- `VISION_MODEL` / `VISION_API_BASE` / `VISION_API_KEY` — vision. The base and
  key inherit the chat values when left blank, so one provider can serve both.
- When a key is blank, LiteLLM falls back to the provider's own environment
  variable (`OPENAI_API_KEY`, `ZAI_API_KEY`, ...); `OPENAI_API_KEY` also acts as
  a generic api_key fallback for both roles.

Example — ClinePass with `qwen3.7-plus` (multimodal, so it serves both roles).
Cline requires `modelType/model` (e.g. `cline-pass/...`); LiteLLM's `openai/`
prefix is only for routing and is stripped before the request:

```
LLM_MODEL=openai/cline-pass/qwen3.7-plus
LLM_API_BASE=https://api.cline.bot/api/v1
LLM_API_KEY=<clinepass key>                    # or: export LLM_API_KEY=$CLINE_API_KEY
VISION_MODEL=openai/cline-pass/qwen3.7-plus    # base/key inherited from LLM_*
```

Some coding-plan proxies accept a multimodal model but still reject image
inputs. Confirm your endpoint actually passes images before relying on it:

```bash
uv run python scripts/check_vision.py             # uses a generated test image
uv run python scripts/check_vision.py --image photo.jpg
```

When `LLM_API_BASE` / `VISION_API_BASE` is set, the app talks OpenAI-compatible
HTTP directly (and unwraps envelopes like Cline's `{data, success}` wrapper).
Without a custom base, requests go through LiteLLM's native providers.

See `.env.example` for more recipes (e.g. the Z.AI GLM Coding Plan for chat plus
a separate vision provider).

## API

- `GET /healthz`
- `POST /api/identify` — multipart form (`description`, `known_attributes` JSON string,
  `conversation` JSON string, optional `images` files) → candidates + `locked` flag
- `POST /api/research` — locked item JSON → `price_range` / `demand` / `marketing_angle` / `sources`
- `POST /api/listing` — item + approved research JSON → per-marketplace title/description
  (Facebook Marketplace, OfferUp); returns `400` if `research_approved` is not `true`

## Quality Checks

```bash
pwsh -NoProfile -File ./scripts/validate.ps1 -All
```

Or individually: `uv run pytest`, `uv run ruff check .`, `uv run basedpyright`,
and `cd frontend && pnpm test && pnpm build`.

## Development Status

Backend (identify/research/listing verticals on FastAPI + LiteLLM + Tavily) and frontend
(Vite + React wizard) are implemented and verified. Containerization (Docker +
docker-compose) and CI/deploy scaffolding (GitHub Actions + Terraform) are in place; see
[docs/plan.md](docs/plan.md) for the full project plan. Deploy workflows are manual-only
and have not been run — nothing is deployed yet.
