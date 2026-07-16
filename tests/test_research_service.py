import json
from unittest.mock import AsyncMock

from app.schemas.research import ResearchRequest
from app.services.research import MAX_SEARCH_QUERY_LEN, ResearchService
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


async def test_research_drops_noise_attributes_from_tavily_query() -> None:
    """Identify provenance blobs must not blow past Tavily's 400-char query limit."""
    search = AsyncMock()
    search.search = AsyncMock(return_value=[])
    llm = AsyncMock()
    llm.chat = AsyncMock(return_value="{}")

    bloated_matches = "x" * 500
    service = ResearchService(llm, search)
    request = ResearchRequest(
        item_name="Vintage Blue Jeans",
        brand="Levi's",
        model="501",
        attributes={
            "size": "32",
            "color": "blue",
            "style": "vintage",
            "search_matches": bloated_matches,
            "reasoning": "long explanation " * 40,
        },
    )

    await service.research(request)

    assert search.search.await_count == 2
    for call in search.search.await_args_list:
        query = call.kwargs.get("query") or call.args[0]
        assert len(query) <= MAX_SEARCH_QUERY_LEN
        assert "search_matches" not in query
        assert bloated_matches not in query
        assert "Levi's" in query
        assert "501" in query
        assert "size: 32" in query
