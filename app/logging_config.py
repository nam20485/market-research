"""Application logging setup.

Call `configure_logging()` once at process/app startup so uvicorn and the
app share a consistent format. Safe for tests — configuring more than once
is a no-op when handlers already exist on the root logger with our marker.
"""

from __future__ import annotations

import logging
import os

_CONFIGURED_ATTR = "_market_research_configured"


def configure_logging(*, level: str | None = None) -> None:
    """Configure root logging if not already configured by this module."""
    root = logging.getLogger()
    if getattr(root, _CONFIGURED_ATTR, False):
        return

    resolved = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()
    logging.basicConfig(
        level=resolved,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=False,
    )
    # Ensure our app loggers are at least INFO even if uvicorn raised the bar.
    logging.getLogger("app").setLevel(resolved)
    setattr(root, _CONFIGURED_ATTR, True)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the `app.` prefix when needed."""
    if name.startswith("app.") or name == "app":
        return logging.getLogger(name)
    return logging.getLogger(f"app.{name}")
