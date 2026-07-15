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

Requires Python 3.12+.

```bash
uv sync
uv run python main.py
```

Copy `.env.example` to `.env` and set your API keys before running inference features.

## Development Status

Early scaffolding — see [docs/plan.md](docs/plan.md) for the full project plan.
