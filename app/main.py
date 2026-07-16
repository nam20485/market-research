"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import identify, listing, posting, research
from app.config import get_settings
from app.logging_config import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    logger.info("Market Research API starting")
    yield
    logger.info("Market Research API shutting down")


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title="Market Research API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(identify.router, prefix="/api")
    app.include_router(research.router, prefix="/api")
    app.include_router(listing.router, prefix="/api")
    app.include_router(posting.router, prefix="/api")

    logger.info(
        "App created (cors_origins=%s)",
        settings.cors_origins_list,
    )
    return app


app = create_app()
