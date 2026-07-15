import json
from unittest.mock import AsyncMock

from app.schemas.research import ResearchRequest
from app.services.research import ResearchService
from app.services.search import SearchResult


async def test_research_builds_report_from_search_and_llm() -> None:
    search = AsyncMock()
    search.search = AsyncMock(
        return_value=[
            SearchResult(title="Sold: Widget", url="https://example.com/a", snippet="sold for $50"),
            SearchResult(title="Widget listing", url="https://example.com/b", snippet="asking $60"),
        ]
    )
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=json.dumps(
            {
                "price_range": {"low": 45, "high": 65, "currency": "USD", "summary": "$45-$65"},
                "demand": "Steady demand from collectors.",
                "marketing_angle": "Emphasize rarity and condition.",
            }
        )
    )

    service = ResearchService(llm, search)
    request = ResearchRequest(item_name="Widget", brand="Acme", condition="good")

    response = await service.research(request)

    assert response.price_range.low == 45
    assert response.price_range.high == 65
    assert response.demand == "Steady demand from collectors."
    assert response.marketing_angle == "Emphasize rarity and condition."
    assert len(response.sources) == 2
    assert search.search.await_count == 2
    llm.chat.assert_awaited_once()


async def test_research_dedupes_source_urls() -> None:
    duplicate_result = SearchResult(title="Widget", url="https://example.com/a", snippet="x")
    search = AsyncMock()
    search.search = AsyncMock(return_value=[duplicate_result, duplicate_result])
    llm = AsyncMock()
    llm.chat = AsyncMock(return_value="{}")

    service = ResearchService(llm, search)
    request = ResearchRequest(item_name="Widget")

    response = await service.research(request)

    assert len(response.sources) == 1
