"""`POST /api/research` — market research report for the locked item."""

import time

from fastapi import APIRouter, Depends

from app.logging_config import get_logger
from app.schemas.research import ResearchRequest, ResearchResponse
from app.services.cache import CacheBackend, get_cache_backend
from app.services.comps import CompsProvider, get_comps_provider
from app.services.llm import LLMService, get_llm_service
from app.services.research import ResearchService
from app.services.search import SearchProvider, get_search_provider

router = APIRouter(tags=["research"])
logger = get_logger(__name__)


def get_research_service(
    llm: LLMService = Depends(get_llm_service),
    search_provider: SearchProvider = Depends(get_search_provider),
    comps_provider: CompsProvider = Depends(get_comps_provider),
    cache: CacheBackend = Depends(get_cache_backend),
) -> ResearchService:
    return ResearchService(llm, search_provider, comps_provider, cache)


@router.post("/research", response_model=ResearchResponse)
async def research_item(
    payload: ResearchRequest,
    service: ResearchService = Depends(get_research_service),
) -> ResearchResponse:
    started = time.perf_counter()
    logger.info(
        "research request: item=%r brand=%r model=%r",
        payload.item_name,
        payload.brand,
        payload.model,
    )
    try:
        response = await service.research(payload)
    except Exception:
        logger.exception("research failed after %.2fs", time.perf_counter() - started)
        raise
    logger.info(
        "research complete in %.2fs: sources=%d",
        time.perf_counter() - started,
        len(response.sources),
    )
    return response
