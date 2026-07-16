"""`POST /api/listing` — per-marketplace listing content, gated on research approval."""

import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.logging_config import get_logger
from app.schemas.listing import ListingRequest, ListingResponse
from app.services.listing import ListingService, ResearchNotApprovedError
from app.services.llm import LLMService, get_llm_service

router = APIRouter(tags=["listing"])
logger = get_logger(__name__)


def get_listing_service(llm: LLMService = Depends(get_llm_service)) -> ListingService:
    return ListingService(llm)


@router.post("/listing", response_model=ListingResponse)
async def generate_listing(
    payload: ListingRequest,
    service: ListingService = Depends(get_listing_service),
) -> ListingResponse:
    started = time.perf_counter()
    logger.info(
        "listing request: item=%r brand=%r approved=%s",
        payload.item_name,
        payload.brand,
        payload.research_approved,
    )
    try:
        response = await service.generate(payload)
    except ResearchNotApprovedError as exc:
        logger.warning("listing rejected: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception:
        logger.exception("listing failed after %.2fs", time.perf_counter() - started)
        raise
    logger.info("listing complete in %.2fs", time.perf_counter() - started)
    return response
