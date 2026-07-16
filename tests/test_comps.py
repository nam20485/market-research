from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.cache import NullCacheBackend
from app.services.comps import (
    Comp,
    NullCompsProvider,
    SerpApiCompsProvider,
    get_comps_provider,
)


def _fake_response(body: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = body
    response.raise_for_status = MagicMock()
    return response


async def test_serpapi_parses_organic_results_with_extracted_price() -> None:
    settings = Settings(serpapi_api_key="serp-test")
    provider = SerpApiCompsProvider(settings, cache=NullCacheBackend())

    body = {
        "organic_results": [
            {
                "title": "Widget - Sold",
                "link": "https://www.ebay.com/itm/1",
                "price": {"raw": "$80.95", "extracted": 80.95},
                "condition": "Brand New",
                "sold_date": "Aug 28, 2025",
            }
        ]
    }
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=_fake_response(body))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.comps.httpx.AsyncClient", return_value=fake_client):
        comps = await provider.sold_comps("widget", max_results=8)

    assert comps == [
        Comp(
            title="Widget - Sold",
            price=80.95,
            url="https://www.ebay.com/itm/1",
            sold_date="Aug 28, 2025",
            condition="Brand New",
        )
    ]


async def test_serpapi_parses_price_range_as_average() -> None:
    settings = Settings(serpapi_api_key="serp-test")
    provider = SerpApiCompsProvider(settings, cache=NullCacheBackend())

    body = {
        "organic_results": [
            {
                "title": "Widget range",
                "link": "https://www.ebay.com/itm/2",
                "price": {
                    "from": {"raw": "$10.00", "extracted": 10.0},
                    "to": {"raw": "$20.00", "extracted": 20.0},
                },
            }
        ]
    }
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=_fake_response(body))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.comps.httpx.AsyncClient", return_value=fake_client):
        comps = await provider.sold_comps("widget", max_results=8)

    assert comps[0].price == 15.0


async def test_serpapi_falls_back_to_raw_price_string() -> None:
    settings = Settings(serpapi_api_key="serp-test")
    provider = SerpApiCompsProvider(settings, cache=NullCacheBackend())

    body = {
        "organic_results": [{"title": "Widget raw", "link": "u", "price": {"raw": "$1,234.56"}}]
    }
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=_fake_response(body))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.comps.httpx.AsyncClient", return_value=fake_client):
        comps = await provider.sold_comps("widget", max_results=8)

    assert comps[0].price == 1234.56


async def test_serpapi_drops_rows_with_unparseable_price() -> None:
    settings = Settings(serpapi_api_key="serp-test")
    provider = SerpApiCompsProvider(settings, cache=NullCacheBackend())

    body = {
        "organic_results": [
            {"title": "No price field", "link": "u1"},
            {"title": "Empty price", "link": "u2", "price": {}},
            {"title": "Bad raw", "link": "u3", "price": {"raw": "Contact seller"}},
            {"title": "Good", "link": "u4", "price": {"extracted": 42.0}},
        ]
    }
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=_fake_response(body))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.comps.httpx.AsyncClient", return_value=fake_client):
        comps = await provider.sold_comps("widget", max_results=8)

    assert len(comps) == 1
    assert comps[0].title == "Good"


async def test_serpapi_truncates_to_max_results() -> None:
    settings = Settings(serpapi_api_key="serp-test")
    provider = SerpApiCompsProvider(settings, cache=NullCacheBackend())

    body = {
        "organic_results": [
            {"title": f"Item {i}", "link": f"u{i}", "price": {"extracted": float(i)}}
            for i in range(5)
        ]
    }
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=_fake_response(body))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.comps.httpx.AsyncClient", return_value=fake_client):
        comps = await provider.sold_comps("widget", max_results=2)

    assert len(comps) == 2


async def test_serpapi_uses_cache_on_hit_without_calling_httpx() -> None:
    settings = Settings(serpapi_api_key="serp-test")
    cache = AsyncMock()
    cache.get = AsyncMock(
        return_value=[
            {"title": "Cached", "price": 10.0, "url": "u", "sold_date": None, "condition": None}
        ]
    )
    provider = SerpApiCompsProvider(settings, cache=cache)

    with patch("app.services.comps.httpx.AsyncClient") as mock_client:
        comps = await provider.sold_comps("widget", max_results=8)

    mock_client.assert_not_called()
    assert comps == [Comp(title="Cached", price=10.0, url="u")]


async def test_serpapi_writes_through_cache_on_miss() -> None:
    settings = Settings(serpapi_api_key="serp-test", cache_ttl_comps_seconds=999)
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    provider = SerpApiCompsProvider(settings, cache=cache)

    body = {"organic_results": [{"title": "Widget", "link": "u", "price": {"extracted": 5.0}}]}
    fake_client = AsyncMock()
    fake_client.get = AsyncMock(return_value=_fake_response(body))
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.comps.httpx.AsyncClient", return_value=fake_client):
        await provider.sold_comps("widget", max_results=8)

    cache.set.assert_awaited_once()
    args, kwargs = cache.set.await_args
    assert kwargs["ttl_seconds"] == 999


async def test_null_comps_provider_returns_empty_list() -> None:
    provider = NullCompsProvider()
    assert await provider.sold_comps("widget", max_results=8) == []


def test_get_comps_provider_returns_serpapi_when_configured() -> None:
    settings = Settings(comps_enabled=True, comps_provider="serpapi", serpapi_api_key="serp-test")
    provider = get_comps_provider(settings, NullCacheBackend())
    assert isinstance(provider, SerpApiCompsProvider)


def test_get_comps_provider_returns_null_when_disabled() -> None:
    settings = Settings(comps_enabled=False)
    provider = get_comps_provider(settings, NullCacheBackend())
    assert isinstance(provider, NullCompsProvider)


def test_get_comps_provider_returns_null_when_key_missing() -> None:
    settings = Settings(comps_enabled=True, comps_provider="serpapi", serpapi_api_key="")
    provider = get_comps_provider(settings, NullCacheBackend())
    assert isinstance(provider, NullCompsProvider)


def test_get_comps_provider_rejects_unknown_provider() -> None:
    settings = Settings(comps_enabled=True, comps_provider="ebay-browse-api")
    with pytest.raises(ValueError, match="Unsupported comps provider"):
        get_comps_provider(settings, NullCacheBackend())
