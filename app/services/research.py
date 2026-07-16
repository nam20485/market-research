"""Market research service: comps + search, then synthesize a priced report."""

from collections.abc import Iterable
from statistics import median
from typing import Any

from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.prompts.research import build_research_prompt
from app.schemas.research import (
    PriceRange,
    PricingConfidence,
    ResearchRequest,
    ResearchResponse,
    SourceLink,
)
from app.services.cache import CacheBackend, build_cache_key
from app.services.comps import Comp, CompsProvider
from app.services.json_utils import parse_json_object
from app.services.llm import LLMService
from app.services.pricing import build_pricing_strategy
from app.services.search import SearchProvider, SearchResult

logger = get_logger(__name__)

MAX_RESULTS_PER_QUERY = 5
# Tavily rejects queries longer than this; leave headroom for query suffixes
# like " sold price used".
MAX_SEARCH_QUERY_LEN = 400
_QUERY_SUFFIX_BUDGET = len(" for sale used marketplace")
# Identify sometimes stuffs provenance blobs into attributes (e.g. search_matches);
# those must not be concatenated into the Tavily query.
_NOISE_ATTRIBUTE_KEYS = frozenset(
    {
        "search_matches",
        "reasoning",
        "evidence",
        "sources",
        "notes",
    }
)
_SEARCH_CACHE_KIND = "research_search"
_SEARCH_CACHE_SCHEMA_VERSION = 1
_NO_FMV_RATIONALE = (
    "No sold comps were found and the model could not estimate a fair market value "
    "from the available search results."
)


class _FmvEstimate(BaseModel):
    """Validates the LLM's fallback `estimated_fmv` field from the parsed report."""

    estimated_fmv: float | None = None


class ResearchService:
    """Gathers sold comps + search hits for the locked item and synthesizes a priced report."""

    def __init__(
        self,
        llm: LLMService,
        search_provider: SearchProvider,
        comps_provider: CompsProvider,
        cache: CacheBackend,
        settings: Settings | None = None,
    ) -> None:
        self._llm = llm
        self._search = search_provider
        self._comps = comps_provider
        self._cache = cache
        self._settings = settings or get_settings()

    async def research(self, request: ResearchRequest) -> ResearchResponse:
        item_label = self._item_label(request)
        logger.info("research: gathering sold comps for %r", item_label)
        comps = await self._comps.sold_comps(
            item_label, max_results=self._settings.comps_max_results
        )
        logger.info("research: got %d sold comps", len(comps))

        results = await self._gather_results(item_label)
        logger.info("research: got %d search hits; synthesizing report", len(results))

        prompt = build_research_prompt(
            item_description=item_label,
            condition=request.condition,
            sold_comps=[f"{c.title}: ${c.price:,.2f} ({c.url})" for c in comps],
            search_results=[f"{r.title}: {r.snippet} ({r.url})" for r in results],
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        parsed = parse_json_object(raw)

        price_range = PriceRange(**parsed.get("price_range", {}))
        sources = _dedupe_sources(SourceLink(title=r.title, url=r.url) for r in results if r.url)
        fmv, confidence, rationale = _resolve_fmv(comps, parsed)

        haggle_pct = (
            request.haggle_pct
            if request.haggle_pct is not None
            else self._settings.default_haggle_pct
        )
        floor_pct = (
            request.floor_pct
            if request.floor_pct is not None
            else self._settings.default_floor_pct
        )
        pricing = build_pricing_strategy(
            fmv,
            haggle_pct=haggle_pct,
            floor_pct=floor_pct,
            condition=request.condition,
            confidence=confidence,
            currency=price_range.currency,
            rationale=rationale,
        )

        logger.info(
            "research: report ready (sources=%d comps=%d fmv=%.2f confidence=%s)",
            len(sources),
            len(comps),
            fmv,
            confidence,
        )
        return ResearchResponse(
            price_range=price_range,
            demand=parsed.get("demand", ""),
            marketing_angle=parsed.get("marketing_angle", ""),
            sources=sources,
            pricing=pricing,
        )

    async def _gather_results(self, item_label: str) -> list[SearchResult]:
        cache_key = build_cache_key(
            item_label, kind=_SEARCH_CACHE_KIND, schema_version=_SEARCH_CACHE_SCHEMA_VERSION
        )
        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.info("research: search cache hit for %r", item_label)
            return [SearchResult.model_validate(item) for item in cached]

        queries = [
            _fit_search_query(f"{item_label} sold price used"),
            _fit_search_query(f"{item_label} for sale used marketplace"),
        ]
        results: list[SearchResult] = []
        for query in queries:
            logger.info("research: search query=%r", query)
            results.extend(await self._search.search(query, max_results=MAX_RESULTS_PER_QUERY))

        await self._cache.set(
            cache_key,
            [r.model_dump() for r in results],
            ttl_seconds=self._settings.cache_ttl_comps_seconds,
        )
        return results

    @staticmethod
    def _item_label(request: ResearchRequest) -> str:
        parts = [request.brand, request.model or request.item_name]
        label = " ".join(part for part in parts if part)
        if request.attributes:
            attrs = ", ".join(
                f"{k}: {_short_attr_value(v)}"
                for k, v in request.attributes.items()
                if k.lower() not in _NOISE_ATTRIBUTE_KEYS and v
            )
            if attrs:
                label = f"{label} ({attrs})"
        # Cap so either query suffix still fits under Tavily's limit.
        max_label = MAX_SEARCH_QUERY_LEN - _QUERY_SUFFIX_BUDGET
        if len(label) > max_label:
            label = label[: max_label - 1].rstrip() + "…"
        return label


def _resolve_fmv(
    comps: list[Comp], parsed: dict[str, Any]
) -> tuple[float, PricingConfidence, str | None]:
    """Compute FMV from sold comps (median), falling back to an LLM estimate.

    Returns `(fmv, confidence, rationale)`. `rationale` is only set when
    neither comps nor a usable LLM estimate were available.
    """
    if comps:
        return median(comp.price for comp in comps), "sold_comps", None

    try:
        estimate = _FmvEstimate.model_validate(parsed)
    except ValidationError:
        estimate = _FmvEstimate()
    if estimate.estimated_fmv is not None:
        return estimate.estimated_fmv, "asking_price", None

    return 0.0, "unknown", _NO_FMV_RATIONALE


def _short_attr_value(value: str, max_len: int = 40) -> str:
    text = value.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _fit_search_query(query: str) -> str:
    if len(query) <= MAX_SEARCH_QUERY_LEN:
        return query
    return query[: MAX_SEARCH_QUERY_LEN - 1].rstrip() + "…"


def _dedupe_sources(sources: Iterable[SourceLink]) -> list[SourceLink]:
    seen: set[str] = set()
    deduped: list[SourceLink] = []
    for source in sources:
        if source.url in seen:
            continue
        seen.add(source.url)
        deduped.append(source)
    return deduped
