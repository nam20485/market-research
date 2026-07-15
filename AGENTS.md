# Repository Guidelines

## Project Structure & Module Organization

`app/` is the FastAPI backend (see `app/main.py`, `app/api/`, `app/services/`,
`app/schemas/`, `app/prompts/`), `frontend/` is the Vite + React + pnpm wizard UI,
`tests/` is the backend pytest suite, and `deploy/tf/` is Terraform for the Cloudflare
Pages project. `main.py` at the repo root is a thin `uvicorn.run(...)` convenience
wrapper around `app.main:app`. `docs/plan.md` is the original design doc (do not edit
it going forward; treat it as historical record).

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
`-Frontend` (`pnpm build`), `-Scan` (uncommitted-secret scan when the skill is
installed). With no switches, `-All` is the default.

Equivalent manual commands:

```bash
uv run pytest         # backend tests (LLM/search mocked, no real network calls)
uv run ruff check .   # lint
uv run basedpyright   # type check
cd frontend && pnpm build  # frontend build check (no dedicated test runner yet)
```

These same checks run in `.github/workflows/ci.yml` on every push/PR to any branch.

## Configuration

API keys and runtime settings go in `.env`. Populate from `.env.example` before running
inference features. Cloudflare/GHCR deploy secrets live in GitHub Actions repo secrets
(`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`), never in `.env` or git.

## CI/CD & Deployment

- CI (`ci.yml`) is safe and non-deploying: it runs on every push/PR.
- All deploy-capable workflows (`cloudflare_deploy.yml`, `publish-backend-image.yml`) are
  `workflow_dispatch`-only and have **not** been run — nothing is deployed. Do not add a
  `push`/`pull_request` trigger to them without explicit instruction; that would violate
  the project's "do not actually deploy yet" constraint.
- `deploy/tf/` provisions the Cloudflare Pages project and its GitHub Actions secrets.
  Never commit `.tfvars` or `terraform.tfstate`. Keep the Terraform
  `cloudflare_pages_project` name identical to the `projectName` used in
  `cloudflare_deploy.yml` — a mismatch there was a known bug in the reference repo this
  was modeled on.

## Commit & Pull Request Guidelines

Git history uses imperative, descriptive commit messages (e.g., "Add initial implementation of market research app with Python 3.12 support..."). Scope changes in the subject; add detail in the body when needed. No PR template exists yet.

## Learned User Preferences

- Prefer dark mode as the default frontend theme, with a persisted light/dark toggle.

## Learned Workspace Facts

- Cloudflare Pages + GitHub Actions deploy scaffolding was modeled on `intel-agency` / `intel-agency-com-v2`; keep the Pages `projectName` identical in Terraform and `cloudflare_deploy.yml`.
- `.env` is loaded via pydantic-settings without shell-style `$VAR` interpolation; LiteLLM provider keys such as `ZAI_API_KEY` (for `zai/` models) must come from the process/container environment, not from expanding variables inside `.env`.
