import json
from unittest.mock import AsyncMock

import pytest

from app.schemas.listing import ListingRequest
from app.services.listing import ListingService, ResearchNotApprovedError


async def test_generate_raises_when_research_not_approved() -> None:
    llm = AsyncMock()
    service = ListingService(llm)
    request = ListingRequest(item_name="Widget", research_approved=False)

    with pytest.raises(ResearchNotApprovedError):
        await service.generate(request)

    llm.chat.assert_not_awaited()


async def test_generate_returns_per_marketplace_copy_when_approved() -> None:
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=json.dumps(
            {
                "facebook_marketplace": {"title": "FB Title", "description": "FB Description"},
                "offerup": {"title": "OU Title", "description": "OU Description"},
            }
        )
    )
    service = ListingService(llm)
    request = ListingRequest(item_name="Widget", research_approved=True, price=42.0)

    response = await service.generate(request)

    assert response.facebook_marketplace.title == "FB Title"
    assert response.offerup.description == "OU Description"
    llm.chat.assert_awaited_once()
