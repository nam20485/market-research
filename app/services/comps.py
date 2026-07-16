"""Sold-comps provider abstraction, with a SerpApi eBay implementation."""

import re
from abc import ABC, abstractmethod
from typing import Any

import httpx
from fastapi import Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.services.cache import CacheBackend, build_cache_key, get_cache_backend

logger = get_logger(__name__)

_SERPAPI_URL = "https://serpapi.com/search.json"
_CACHE_KIND = "sold_comps"
_CACHE_SCHEMA_VERSION = 1


class Comp(BaseModel):
    """A single sold-comp listing used to estimate fair market value."""

    title: str
    price: float
    url: str
    sold_date: str | None = None
    condition: str | None = None


class CompsProvider(ABC):
    """Interface for a sold-listing comps backend used by market research."""

    @abstractmethod
    async def sold_comps(self, query: str, *, max_results: int = 8) -> list[Comp]:
        """Return sold listings matching `query`, most relevant first."""
        raise NotImplementedError


class SerpApiCompsProvider(CompsProvider):
    """Comps provider backed by SerpApi's eBay engine, filtered to sold listings.

    Responses are cached at the provider-response layer via `CacheBackend`
    (keyed on the normalized query) so repeat lookups don't re-spend a
    metered SerpApi call within the TTL window.
    """

    def __init__(self, settings: Settings | None = None, cache: CacheBackend | None = None) -> None:
        self._settings = settings or get_settings()
        self._cache = cache or get_cache_backend(self._settings)

    async def sold_comps(self, query: str, *, max_results: int = 8) -> list[Comp]:
        cache_key = build_cache_key(query, kind=_CACHE_KIND, schema_version=_CACHE_SCHEMA_VERSION)
        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.info("sold comps cache hit: query_len=%d", len(query))
            comps = [Comp.model_validate(item) for item in cached]
            return comps[:max_results]

        comps = await self._fetch(query, max_results=max_results)
        await self._cache.set(
            cache_key,
            [comp.model_dump() for comp in comps],
            ttl_seconds=self._settings.cache_ttl_comps_seconds,
        )
        return comps

    async def _fetch(self, query: str, *, max_results: int) -> list[Comp]:
        params = {
            "engine": "ebay",
            "_nkw": query,
            "show_only": "Sold",
            "ebay_domain": "ebay.com",
            "api_key": self._settings.serpapi_api_key,
        }
        logger.info("serpapi ebay search: query_len=%d max_results=%d", len(query), max_results)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(_SERPAPI_URL, params=params)
            response.raise_for_status()
            body = response.json()

        raw_results = body.get("organic_results", []) if isinstance(body, dict) else []
        comps: list[Comp] = []
        for item in raw_results:
            price = _parse_price(item.get("price"))
            if price is None:
                continue
            comps.append(
                Comp(
                    title=item.get("title", ""),
                    price=price,
                    url=item.get("link", ""),
                    sold_date=item.get("sold_date"),
                    condition=item.get("condition"),
                )
            )
            if len(comps) >= max_results:
                break
        logger.info("serpapi ebay search: parsed %d/%d comps", len(comps), len(raw_results))
        return comps


class NullCompsProvider(CompsProvider):
    """No-op comps provider used when comps are disabled or misconfigured."""

    async def sold_comps(self, query: str, *, max_results: int = 8) -> list[Comp]:
        return []


def _parse_price(price: Any) -> float | None:
    """Parse a SerpApi eBay `price` field (single, range, or raw string) to a float.

    Returns `None` for unparseable rows so the caller can drop them.
    """
    if not isinstance(price, dict):
        return None

    extracted = price.get("extracted")
    if isinstance(extracted, int | float):
        return float(extracted)

    price_from, price_to = price.get("from"), price.get("to")
    if isinstance(price_from, dict) and isinstance(price_to, dict):
        low, high = price_from.get("extracted"), price_to.get("extracted")
        if isinstance(low, int | float) and isinstance(high, int | float):
            return (float(low) + float(high)) / 2

    raw = price.get("raw")
    if isinstance(raw, str):
        match = re.search(r"[\d,]+\.?\d*", raw)
        if match:
            try:
                return float(match.group(0).replace(",", ""))
            except ValueError:
                return None

    return None


def get_comps_provider(
    settings: Settings = Depends(get_settings),
    cache: CacheBackend = Depends(get_cache_backend),
) -> CompsProvider:
    """Factory selecting a comps provider implementation from settings.

    `settings`/`cache` default to FastAPI sub-dependencies so this also works
    as a route dependency without FastAPI mistaking them for request body fields.
    Falls back to `NullCompsProvider` when comps are disabled or the selected
    provider is missing its required API key (graceful degradation).
    """
    if not settings.comps_enabled:
        return NullCompsProvider()
    if settings.comps_provider == "serpapi":
        if not settings.serpapi_api_key:
            logger.warning(
                "comps_provider=serpapi but SERPAPI_API_KEY is blank; using NullCompsProvider"
            )
            return NullCompsProvider()
        return SerpApiCompsProvider(settings, cache)
    raise ValueError(f"Unsupported comps provider: {settings.comps_provider}")
