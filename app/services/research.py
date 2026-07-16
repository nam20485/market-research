"""Market research service: search for comps, then synthesize a structured report."""

from collections.abc import Iterable

from app.logging_config import get_logger
from app.prompts.research import build_research_prompt
from app.schemas.research import PriceRange, ResearchRequest, ResearchResponse, SourceLink
from app.services.json_utils import parse_json_object
from app.services.llm import LLMService
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


class ResearchService:
    """Builds comp search queries for the locked item and synthesizes a report."""

    def __init__(self, llm: LLMService, search_provider: SearchProvider) -> None:
        self._llm = llm
        self._search = search_provider

    async def research(self, request: ResearchRequest) -> ResearchResponse:
        item_label = self._item_label(request)
        logger.info("research: gathering comps for %r", item_label)
        results = await self._gather_results(item_label)
        logger.info("research: got %d search hits; synthesizing report", len(results))

        prompt = build_research_prompt(
            item_description=item_label,
            condition=request.condition,
            search_results=[f"{r.title}: {r.snippet} ({r.url})" for r in results],
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        parsed = parse_json_object(raw)

        price_range = PriceRange(**parsed.get("price_range", {}))
        sources = _dedupe_sources(SourceLink(title=r.title, url=r.url) for r in results if r.url)

        logger.info(
            "research: report ready (sources=%d demand_len=%d)",
            len(sources),
            len(str(parsed.get("demand", ""))),
        )
        return ResearchResponse(
            price_range=price_range,
            demand=parsed.get("demand", ""),
            marketing_angle=parsed.get("marketing_angle", ""),
            sources=sources,
        )

    async def _gather_results(self, item_label: str) -> list[SearchResult]:
        queries = [
            _fit_search_query(f"{item_label} sold price used"),
            _fit_search_query(f"{item_label} for sale used marketplace"),
        ]
        results: list[SearchResult] = []
        for query in queries:
            logger.info("research: search query=%r", query)
            results.extend(await self._search.search(query, max_results=MAX_RESULTS_PER_QUERY))
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
