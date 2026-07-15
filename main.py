"""Convenience entry point: `uv run python main.py` starts the FastAPI dev server.

Equivalent to `uv run uvicorn app.main:app --reload --port 8000`.
"""

import uvicorn


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
