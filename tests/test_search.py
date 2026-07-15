from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.services.search import SearchResult, TavilySearchProvider, get_search_provider


async def test_tavily_search_maps_results_to_search_result() -> None:
    settings = Settings(tavily_api_key="tvly-test")
    provider = TavilySearchProvider(settings)

    fake_response = {
        "results": [
            {"title": "Widget for sale", "url": "https://example.com/1", "content": "Great widget"},
            {"title": "Widget sold", "url": "https://example.com/2", "content": "Sold last week"},
        ]
    }
    fake_client = AsyncMock()
    fake_client.search = AsyncMock(return_value=fake_response)

    with patch.object(provider, "_client", new=fake_client):
        results = await provider.search("widget", max_results=2)

    assert results == [
        SearchResult(title="Widget for sale", url="https://example.com/1", snippet="Great widget"),
        SearchResult(title="Widget sold", url="https://example.com/2", snippet="Sold last week"),
    ]


def test_get_search_provider_returns_tavily_for_default_setting() -> None:
    settings = Settings(search_provider="tavily", tavily_api_key="tvly-test")
    provider = get_search_provider(settings)
    assert isinstance(provider, TavilySearchProvider)


def test_get_search_provider_rejects_unknown_provider() -> None:
    settings = Settings(search_provider="bing")
    with pytest.raises(ValueError, match="Unsupported search provider"):
        get_search_provider(settings)
