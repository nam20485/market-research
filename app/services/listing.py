"""Listing generation service: formats copy-paste-ready marketplace listing content."""

from app.prompts.listing import build_listing_prompt
from app.schemas.listing import ListingRequest, ListingResponse, MarketplaceListing
from app.services.json_utils import parse_json_object
from app.services.llm import LLMService


class ResearchNotApprovedError(Exception):
    """Raised when a listing is requested before the research report is approved."""


class ListingService:
    """Generates per-marketplace listing copy, gated on research approval."""

    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    async def generate(self, request: ListingRequest) -> ListingResponse:
        if not request.research_approved:
            raise ResearchNotApprovedError(
                "Listing generation requires an approved market research report."
            )

        item_label = self._item_label(request)
        prompt = build_listing_prompt(
            item_description=item_label,
            condition=request.condition,
            price=request.price,
            research_summary=request.research_summary,
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        parsed = parse_json_object(raw)

        return ListingResponse(
            facebook_marketplace=MarketplaceListing(**parsed.get("facebook_marketplace", {})),
            offerup=MarketplaceListing(**parsed.get("offerup", {})),
        )

    @staticmethod
    def _item_label(request: ListingRequest) -> str:
        parts = [request.brand, request.model or request.item_name]
        label = " ".join(part for part in parts if part)
        if request.attributes:
            attrs = ", ".join(f"{k}: {v}" for k, v in request.attributes.items())
            label = f"{label} ({attrs})"
        return label
