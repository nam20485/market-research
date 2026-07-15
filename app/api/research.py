"""`POST /api/research` — market research report for the locked item."""

from fastapi import APIRouter, Depends

from app.schemas.research import ResearchRequest, ResearchResponse
from app.services.llm import LLMService, get_llm_service
from app.services.research import ResearchService
from app.services.search import SearchProvider, get_search_provider

router = APIRouter(tags=["research"])


def get_research_service(
    llm: LLMService = Depends(get_llm_service),
    search_provider: SearchProvider = Depends(get_search_provider),
) -> ResearchService:
    return ResearchService(llm, search_provider)


@router.post("/research", response_model=ResearchResponse)
async def research_item(
    payload: ResearchRequest,
    service: ResearchService = Depends(get_research_service),
) -> ResearchResponse:
    return await service.research(payload)
