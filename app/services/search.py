"""Web search provider abstraction, with a Tavily implementation."""

from abc import ABC, abstractmethod

from fastapi import Depends
from pydantic import BaseModel
from tavily import AsyncTavilyClient

from app.config import Settings, get_settings


class SearchResult(BaseModel):
    """A single structured search result."""

    title: str
    url: str
    snippet: str = ""


class SearchProvider(ABC):
    """Interface for a web search backend used by identification and research."""

    @abstractmethod
    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """Run a search query and return structured results."""
        raise NotImplementedError


class TavilySearchProvider(SearchProvider):
    """Search provider backed by the Tavily search API."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = AsyncTavilyClient(api_key=self._settings.tavily_api_key)

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        response = await self._client.search(query=query, max_results=max_results)
        results = response.get("results", []) if isinstance(response, dict) else []
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
            )
            for item in results
        ]


def get_search_provider(settings: Settings = Depends(get_settings)) -> SearchProvider:
    """Factory selecting a search provider implementation from settings.

    `settings` defaults to a FastAPI sub-dependency (`Depends(get_settings)`) so this
    also works as a route dependency without FastAPI mistaking it for a request body field.
    """
    if settings.search_provider == "tavily":
        return TavilySearchProvider(settings)
    raise ValueError(f"Unsupported search provider: {settings.search_provider}")
