"""`GET /api/post/capabilities`, `POST /api/post/fill` — local-only marketplace auto-fill."""

import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.schemas.posting import FillResponse, MarketplaceInfo, PostingCapabilities
from app.services.posting.agent import fill as run_fill
from app.services.posting.profiles import get_profile, list_profiles
from app.services.posting.session import open_browser_session

router = APIRouter(prefix="/post", tags=["posting"])
logger = get_logger(__name__)


@router.get("/capabilities", response_model=PostingCapabilities)
async def get_capabilities(
    settings: Settings = Depends(get_settings),
) -> PostingCapabilities:
    if not settings.posting_enabled:
        return PostingCapabilities(enabled=False, marketplaces=[])
    return PostingCapabilities(
        enabled=True,
        marketplaces=[
            MarketplaceInfo(id=profile.id, label=profile.label) for profile in list_profiles()
        ],
    )


@router.post("/fill", response_model=FillResponse)
async def fill_marketplace_listing(
    marketplace: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    price: float | None = Form(default=None),
    images: list[UploadFile] = File(default=[]),
    settings: Settings = Depends(get_settings),
) -> FillResponse:
    if not settings.posting_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Marketplace posting is disabled."
        )
    profile = get_profile(marketplace)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown marketplace: {marketplace!r}",
        )

    started = time.perf_counter()
    logger.info(
        "posting fill request: marketplace=%s title_len=%d images=%d",
        marketplace,
        len(title),
        len(images),
    )

    with tempfile.TemporaryDirectory(prefix="market-research-posting-") as tmp_dir:
        image_paths = await _save_temp_images(images, Path(tmp_dir))
        try:
            async with open_browser_session(settings) as session:
                steps = await run_fill(
                    session,
                    profile,
                    title=title,
                    description=description,
                    price=price,
                    image_paths=image_paths,
                    settings=settings,
                )
        except Exception as exc:
            logger.exception(
                "posting fill failed after %.2fs", time.perf_counter() - started
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Failed to fill the marketplace listing. Make sure Chrome is running "
                    "locally with remote debugging enabled (chrome://inspect/#remote-debugging) "
                    "and try again."
                ),
            ) from exc

    logger.info(
        "posting fill complete in %.2fs: steps=%d", time.perf_counter() - started, len(steps)
    )
    return FillResponse(status="filled", steps_summary=steps)


async def _save_temp_images(images: list[UploadFile], tmp_dir: Path) -> list[str]:
    """Write uploaded photos to `tmp_dir` and return their absolute paths.

    Callers own `tmp_dir`'s lifecycle (a `finally`-backed `TemporaryDirectory`),
    so these files are cleaned up automatically once the request completes.
    """
    paths: list[str] = []
    for index, image in enumerate(images):
        if not image.filename:
            continue
        suffix = Path(image.filename).suffix or ".jpg"
        dest = tmp_dir / f"photo_{index}{suffix}"
        dest.write_bytes(await image.read())
        paths.append(str(dest))
    return paths
