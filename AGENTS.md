# Repository Guidelines

## Project Structure & Module Organization

`app/` is the FastAPI backend (see `app/main.py`, `app/api/`, `app/services/`,
`app/schemas/`, `app/prompts/`), `frontend/` is the Vite + React + pnpm wizard UI,
`tests/` is the backend pytest suite, and `deploy/tf/` is Terraform for the Cloudflare
Pages project and the GCP Cloud Run backend. `main.py` at the repo root is a thin
`uvicorn.run(...)` convenience wrapper around `app.main:app`. `docs/plan.md` is the
original design doc (do not edit it going forward; treat it as historical record).

Configuration uses `.env` (copy from `.env.example`; `.env` is gitignored). Both the
backend and frontend can also run inside containers via the root `Dockerfile` +
`frontend/Dockerfile` + `docker-compose.yml`.

## Build, Test, and Development Commands

Requires Python 3.12 (pinned in `.python-version`) and Node 24+/pnpm for the frontend.

```bash
uv sync                                          # install backend dependencies
uv run python main.py                            # run entry point
uv run uvicorn app.main:app --reload --port 8000 # equivalent, explicit
uv build                                         # build sdist and wheel

cd frontend && pnpm install && pnpm dev          # run frontend dev server

docker compose up --build                        # run both services in containers
```

## Testing & Quality Gates

Preferred single entry point (mirrors CI):

```bash
pwsh -NoProfile -File ./scripts/validate.ps1 -All
```

Switches: `-Lint` (ruff), `-Typecheck` (basedpyright), `-Test` (pytest),
`-Frontend` (`pnpm test` + `pnpm build`), `-Scan` (uncommitted-secret scan when the skill is
installed). With no switches, `-All` is the default.

Equivalent manual commands:

```bash
uv run pytest         # backend tests (LLM/search mocked, no real network calls)
uv run ruff check .   # lint
uv run basedpyright   # type check
cd frontend && pnpm test && pnpm build  # API client tests + production build
```

These same checks run in `.github/workflows/ci.yml` on every push/PR to any branch.

## Configuration

API keys and runtime settings go in `.env`. Populate from `.env.example` before running
inference features. Cloudflare/GCP deploy secrets live in GitHub Actions repo secrets
(`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `GCP_SA_KEY`), never in `.env` or git.
Cloud Run's runtime secrets (LLM/vision/OpenAI/Tavily/ZAI API keys) live in GCP Secret
Manager, populated via `gcloud secrets versions add`, also never in `.env` or git.

Do not conflate the two backend URL env vars:

- `BACKEND_PROXY_TARGET` — server-only (Compose / Vite config). Points the Vite proxy at
  `http://backend:8000` on the Compose network. Must **not** use the `VITE_` prefix, or
  the Docker-internal hostname is baked into the browser bundle and client fetch fails.
- `VITE_BACKEND_URL` — browser-facing. Leave unset for local/Compose (relative `/api` +
  proxy). Set only for Cloudflare Pages builds to the public Cloud Run origin.

## CI/CD & Deployment

- CI (`ci.yml`) is safe and non-deploying: it runs on every push/PR.
- All deploy-capable workflows (`cloudflare_deploy.yml`, `google-cloudrun-deploy.yml`,
  `publish-backend-image.yml`) are `workflow_dispatch`-only and have **not** been run —
  nothing is deployed. Do not add a `push`/`pull_request` trigger to them without explicit
  instruction; that would violate the project's "do not actually deploy yet" constraint.
- Backend deploy target is now Google Cloud Run (not just GHCR): `google-cloudrun-deploy.yml`
  builds/pushes a SHA-tagged image to Artifact Registry and deploys the
  `market-research-backend` Cloud Run service in `us-central1`, authenticated via a
  Service Account key (`secrets.GCP_SA_KEY`), not WIF. Free-tier-friendly with
  `min_instance_count = 0` (scale-to-zero). `publish-backend-image.yml` (GHCR) is now
  superseded/dormant — kept for reference only.
- `deploy/tf/` provisions the Cloudflare Pages project AND the GCP Cloud Run backend
  (Artifact Registry repo, deploy + runtime service accounts, Secret Manager secret
  containers, the Cloud Run service) in one Terraform state, and pushes CI secrets/vars
  (`GCP_SA_KEY` secret, `VITE_BACKEND_URL` and `GCP_PROJECT_ID` variables) into GitHub Actions.
  Never commit `.tfvars` or `terraform.tfstate` (the SA key also lands in local tfstate —
  keep it gitignored). Keep the Terraform `cloudflare_pages_project` name identical to the
  `projectName` used in `cloudflare_deploy.yml` — a mismatch there was a known bug in the
  reference repo this was modeled on.
- Frontend/backend topology is two independent deploys, not a unified Worker: Cloudflare
  Pages (frontend) calls the Cloud Run backend directly, cross-origin, at build-time-baked
  `VITE_BACKEND_URL`. They're coupled only via CORS (`CORS_ORIGINS` env / `frontend_origin`
  Terraform var), not same-origin routing.
- Cloud Run is public via `allUsers` / `roles/run.invoker`. An org policy that blocks
  `allUsers` will break browser access; personal accounts are usually fine.
- Cloud Run secret values (`LLM_API_KEY`, `VISION_API_KEY`, `OPENAI_API_KEY`,
  `TAVILY_API_KEY`, `ZAI_API_KEY`) are added out-of-band via
  `gcloud secrets versions add <NAME> --data-file=-` — Terraform only creates the Secret
  Manager containers, never the values, so they never land in tfstate or git.

## Commit & Pull Request Guidelines

Git history uses imperative, descriptive commit messages (e.g., "Add initial implementation of market research app with Python 3.12 support..."). Scope changes in the subject; add detail in the body when needed. No PR template exists yet.

## Learned User Preferences

- Prefer dark mode as the default frontend theme, with a persisted light/dark toggle.
- Prefer frontend work to reach ≥95% test coverage before treating it as done.

## Learned Workspace Facts

- Cloudflare Pages + GitHub Actions deploy scaffolding was modeled on `intel-agency` / `intel-agency-com-v2`; keep the Pages `projectName` identical in Terraform and `cloudflare_deploy.yml`.
- Backend production hosting is Google Cloud Run (service `market-research-backend`,
  region `us-central1`, image in Artifact Registry repo `market-research`), deployed via
  `google-cloudrun-deploy.yml`. `publish-backend-image.yml` (GHCR,
  `ghcr.io/<owner>/<repo>-backend`) is superseded/dormant, kept only for reference.
  Frontend deploys to Cloudflare Pages.
- Compose must set `BACKEND_PROXY_TARGET=http://backend:8000` for the Vite server proxy —
  never `VITE_BACKEND_URL` (that bakes `backend` into the browser and causes
  "Failed to fetch"). Pages builds use `VITE_BACKEND_URL` for the public Cloud Run URL.
- Research search queries must stay ≤400 chars (Tavily limit). Identify can stuff large
  provenance into attributes (`search_matches`, `reasoning`); `ResearchService` drops those
  noise keys and caps query length — do not reintroduce raw attribute dumps into Tavily
  queries.
- `.env` is loaded via pydantic-settings without shell-style `$VAR` interpolation; LiteLLM provider keys such as `ZAI_API_KEY` (for `zai/` models) must come from the process/container environment, not from expanding variables inside `.env`.
- OpenAI-compatible providers use the `openai/<model>` LiteLLM prefix with `LLM_API_BASE` / `LLM_API_KEY` (and optional `VISION_*`; blank vision base/key inherit from LLM). Z.AI coding plan (`zai/`) is text-only — point vision at a separate provider.
- Frontend has no router, no component library, and no global state library (React 19 + `useState`/props only); Tailwind is loaded via a CDN script in `index.html`, not a build step. Client-side persisted state (theme, recent search queries) uses small custom hooks that read/write `localStorage` directly and guard against missing/corrupt JSON — follow the `useTheme.js` pattern (e.g. `useRecentQueries.js`) for new persisted UI state.
- Backend structured logging lives in `app/logging_config.py` (`LOG_LEVEL` env, default `INFO`); API routes and services log start/duration/success-fail. The frontend mirrors this with a `StatusLog` component showing progressive step updates and `[market-research]`-prefixed browser console logs, so long-running requests don't look hung.
