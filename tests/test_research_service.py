import json
from unittest.mock import AsyncMock

from app.config import Settings
from app.schemas.research import ResearchRequest
from app.services.cache import NullCacheBackend
from app.services.comps import Comp
from app.services.research import MAX_SEARCH_QUERY_LEN, ResearchService
from app.services.search import SearchResult


def _service(
    llm: AsyncMock,
    search: AsyncMock,
    comps: AsyncMock | None = None,
    cache: AsyncMock | None = None,
    settings: Settings | None = None,
) -> ResearchService:
    comps_provider = comps or _comps_provider([])
    cache_backend = cache if cache is not None else NullCacheBackend()
    return ResearchService(llm, search, comps_provider, cache_backend, settings)


def _comps_provider(comps: list[Comp]) -> AsyncMock:
    provider = AsyncMock()
    provider.sold_comps = AsyncMock(return_value=comps)
    return provider


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
                "estimated_fmv": 55,
            }
        )
    )

    service = _service(llm, search)
    request = ResearchRequest(item_name="Widget", brand="Acme", condition="good")

    response = await service.research(request)

    assert response.price_range.low == 45
    assert response.price_range.high == 65
    assert response.demand == "Steady demand from collectors."
    assert response.marketing_angle == "Emphasize rarity and condition."
    assert len(response.sources) == 2
    assert search.search.await_count == 2
    llm.chat.assert_awaited_once()
    assert response.pricing.confidence == "asking_price"
    assert response.pricing.fmv == 55.0


async def test_research_dedupes_source_urls() -> None:
    duplicate_result = SearchResult(title="Widget", url="https://example.com/a", snippet="x")
    search = AsyncMock()
    search.search = AsyncMock(return_value=[duplicate_result, duplicate_result])
    llm = AsyncMock()
    llm.chat = AsyncMock(return_value="{}")

    service = _service(llm, search)
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
    service = _service(llm, search)
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


async def test_research_uses_median_of_sold_comps_as_fmv() -> None:
    search = AsyncMock()
    search.search = AsyncMock(return_value=[])
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=json.dumps(
            {
                "price_range": {"low": 40, "high": 60, "currency": "USD", "summary": "$40-$60"},
                "demand": "Steady.",
                "marketing_angle": "Highlight condition.",
            }
        )
    )
    comps = _comps_provider(
        [
            Comp(title="Sold 1", price=40.0, url="https://example.com/c1"),
            Comp(title="Sold 2", price=50.0, url="https://example.com/c2"),
            Comp(title="Sold 3", price=90.0, url="https://example.com/c3"),
        ]
    )
    settings = Settings(comps_max_results=8, default_haggle_pct=0.15, default_floor_pct=0.10)

    service = _service(llm, search, comps=comps, settings=settings)
    request = ResearchRequest(item_name="Widget", condition="like-new")

    response = await service.research(request)

    assert response.pricing.confidence == "sold_comps"
    assert response.pricing.fmv == 50.0
    assert response.pricing.condition_multiplier == 1.0
    assert response.pricing.listing_price == round(50.0 * 1.15, 2)
    assert response.pricing.firm_bottom == round(50.0 * 0.90, 2)
    comps.sold_comps.assert_awaited_once()
    call_kwargs = comps.sold_comps.await_args.kwargs
    assert call_kwargs["max_results"] == 8


async def test_research_falls_back_to_tavily_and_llm_estimate_when_no_comps() -> None:
    search = AsyncMock()
    search.search = AsyncMock(
        return_value=[SearchResult(title="Asking $70", url="https://example.com/a", snippet="x")]
    )
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=json.dumps(
            {
                "price_range": {"low": 60, "high": 80, "currency": "USD", "summary": "$60-$80"},
                "demand": "Moderate.",
                "marketing_angle": "Focus on scarcity.",
                "estimated_fmv": 70,
            }
        )
    )
    comps = _comps_provider([])

    service = _service(llm, search, comps=comps)
    request = ResearchRequest(item_name="Widget", condition="fair")

    response = await service.research(request)

    assert response.pricing.confidence == "asking_price"
    assert response.pricing.fmv == 70.0
    assert response.pricing.condition_multiplier == 0.75


async def test_research_falls_back_to_unknown_confidence_when_llm_gives_no_fmv() -> None:
    search = AsyncMock()
    search.search = AsyncMock(return_value=[])
    llm = AsyncMock()
    llm.chat = AsyncMock(
        return_value=json.dumps(
            {
                "price_range": {},
                "demand": "Unclear.",
                "marketing_angle": "Not enough data.",
            }
        )
    )
    comps = _comps_provider([])

    service = _service(llm, search, comps=comps)
    request = ResearchRequest(item_name="Widget")

    response = await service.research(request)

    assert response.pricing.confidence == "unknown"
    assert response.pricing.fmv == 0.0
    assert response.pricing.rationale


async def test_research_applies_condition_multiplier_and_haggle_overrides() -> None:
    search = AsyncMock()
    search.search = AsyncMock(return_value=[])
    llm = AsyncMock()
    llm.chat = AsyncMock(return_value="{}")
    comps = _comps_provider([Comp(title="Sold", price=100.0, url="https://example.com/c1")])

    service = _service(llm, search, comps=comps)
    request = ResearchRequest(
        item_name="Widget", condition="new", haggle_pct=0.25, floor_pct=0.20
    )

    response = await service.research(request)

    assert response.pricing.condition_multiplier == 1.10
    assert response.pricing.haggle_pct == 0.25
    assert response.pricing.floor_pct == 0.20
    assert response.pricing.listing_price == round(100.0 * 1.25 * 1.10, 2)
    assert response.pricing.firm_bottom == round(100.0 * 0.80 * 1.10, 2)


async def test_research_search_cache_hit_skips_search_provider() -> None:
    search = AsyncMock()
    search.search = AsyncMock(return_value=[])
    llm = AsyncMock()
    llm.chat = AsyncMock(return_value="{}")
    comps = _comps_provider([])
    cache = AsyncMock()
    cache.get = AsyncMock(
        return_value=[
            {"title": "Cached hit", "url": "https://example.com/cached", "snippet": "cached"}
        ]
    )
    cache.set = AsyncMock()

    service = _service(llm, search, comps=comps, cache=cache)
    request = ResearchRequest(item_name="Widget")

    response = await service.research(request)

    search.search.assert_not_called()
    cache.set.assert_not_called()
    assert any(source.url == "https://example.com/cached" for source in response.sources)


async def test_research_search_cache_miss_writes_through_cache() -> None:
    search = AsyncMock()
    search.search = AsyncMock(
        return_value=[SearchResult(title="Fresh", url="https://example.com/fresh", snippet="x")]
    )
    llm = AsyncMock()
    llm.chat = AsyncMock(return_value="{}")
    comps = _comps_provider([])
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    settings = Settings(cache_ttl_comps_seconds=1234)

    service = _service(llm, search, comps=comps, cache=cache, settings=settings)
    request = ResearchRequest(item_name="Widget")

    await service.research(request)

    cache.set.assert_awaited_once()
    args, kwargs = cache.set.await_args
    assert kwargs["ttl_seconds"] == 1234
