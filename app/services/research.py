"""Market research service: search for comps, then synthesize a structured report."""

from collections.abc import Iterable

from app.prompts.research import build_research_prompt
from app.schemas.research import PriceRange, ResearchRequest, ResearchResponse, SourceLink
from app.services.json_utils import parse_json_object
from app.services.llm import LLMService
from app.services.search import SearchProvider, SearchResult

MAX_RESULTS_PER_QUERY = 5


class ResearchService:
    """Builds comp search queries for the locked item and synthesizes a report."""

    def __init__(self, llm: LLMService, search_provider: SearchProvider) -> None:
        self._llm = llm
        self._search = search_provider

    async def research(self, request: ResearchRequest) -> ResearchResponse:
        item_label = self._item_label(request)
        results = await self._gather_results(item_label)

        prompt = build_research_prompt(
            item_description=item_label,
            condition=request.condition,
            search_results=[f"{r.title}: {r.snippet} ({r.url})" for r in results],
        )
        raw = await self._llm.chat([{"role": "user", "content": prompt}])
        parsed = parse_json_object(raw)

        price_range = PriceRange(**parsed.get("price_range", {}))
        sources = _dedupe_sources(SourceLink(title=r.title, url=r.url) for r in results if r.url)

        return ResearchResponse(
            price_range=price_range,
            demand=parsed.get("demand", ""),
            marketing_angle=parsed.get("marketing_angle", ""),
            sources=sources,
        )

    async def _gather_results(self, item_label: str) -> list[SearchResult]:
        queries = [
            f"{item_label} sold price used",
            f"{item_label} for sale used marketplace",
        ]
        results: list[SearchResult] = []
        for query in queries:
            results.extend(await self._search.search(query, max_results=MAX_RESULTS_PER_QUERY))
        return results

    @staticmethod
    def _item_label(request: ResearchRequest) -> str:
        parts = [request.brand, request.model or request.item_name]
        label = " ".join(part for part in parts if part)
        if request.attributes:
            attrs = ", ".join(f"{k}: {v}" for k, v in request.attributes.items())
            label = f"{label} ({attrs})"
        return label


def _dedupe_sources(sources: Iterable[SourceLink]) -> list[SourceLink]:
    seen: set[str] = set()
    deduped: list[SourceLink] = []
    for source in sources:
        if source.url in seen:
            continue
        seen.add(source.url)
        deduped.append(source)
    return deduped
