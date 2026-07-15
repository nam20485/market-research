"""`POST /api/listing` — per-marketplace listing content, gated on research approval."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.listing import ListingRequest, ListingResponse
from app.services.listing import ListingService, ResearchNotApprovedError
from app.services.llm import LLMService, get_llm_service

router = APIRouter(tags=["listing"])


def get_listing_service(llm: LLMService = Depends(get_llm_service)) -> ListingService:
    return ListingService(llm)


@router.post("/listing", response_model=ListingResponse)
async def generate_listing(
    payload: ListingRequest,
    service: ListingService = Depends(get_listing_service),
) -> ListingResponse:
    try:
        return await service.generate(payload)
    except ResearchNotApprovedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
