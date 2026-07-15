# Repository Guidelines

## Project Structure & Module Organization

Early scaffolding. `main.py` is the sole entry point (hello-world placeholder). `pyproject.toml` defines the Python 3.12 package managed by uv. `docs/plan.md` is the authoritative design doc for the planned three-stage workflow: item identification, market research, and listing generation for Facebook Marketplace and OfferUp.

Planned but not yet implemented: FastAPI backend, LiteLLM inference layer, Vite frontend, Docker/docker-compose. Configuration will use `.env` (copy from `.env.example`; `.env` is gitignored). Deployment is deferred — local development only for now.

## Build, Test, and Development Commands

Requires Python 3.12 (pinned in `.python-version`).

```bash
uv sync                              # install dependencies
uv run python main.py                # run entry point
uv build                             # build sdist and wheel
```

No test runner or single-test command is configured yet.

## Configuration

API keys and runtime settings go in `.env`. Populate from `.env.example` before running inference features once LiteLLM is integrated.

## Commit & Pull Request Guidelines

Git history uses imperative, descriptive commit messages (e.g., "Add initial implementation of market research app with Python 3.12 support..."). Scope changes in the subject; add detail in the body when needed. No PR template or `.github` workflows exist yet.
