"""Application settings loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def _call_kwargs(api_base: str, api_key: str) -> dict[str, str]:
    """Build LiteLLM keyword overrides, omitting blanks.

    A blank value is left out entirely so LiteLLM falls back to its own
    resolution (e.g. reading OPENAI_API_KEY / ZAI_API_KEY from the process
    environment for the relevant provider prefix).
    """
    kwargs: dict[str, str] = {}
    if api_base:
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key
    return kwargs


class Settings(BaseSettings):
    """Runtime configuration.

    Field names mirror the keys documented in `.env.example`.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Chat model — market research + listing generation.
    llm_model: str = "gpt-4o-mini"
    llm_api_base: str = ""
    llm_api_key: str = ""

    # Vision model — item identification. When the vision-specific base/key are
    # blank they inherit the chat model's values, so a single provider can serve
    # both roles (e.g. one ClinePass subscription with a multimodal model).
    vision_model: str = "gpt-4o-mini"
    vision_api_base: str = ""
    vision_api_key: str = ""

    # Plain-OpenAI convenience: used as the api_key fallback for both roles.
    openai_api_key: str = ""

    search_provider: str = "tavily"
    tavily_api_key: str = ""
    cors_origins: str = "http://localhost:5173"

    # eBay sold-comps lookup (used for FMV pricing research).
    comps_provider: str = "serpapi"
    comps_enabled: bool = True
    comps_max_results: int = 8
    serpapi_api_key: str = ""

    # Local cache for provider responses (sold comps, identity lookups).
    cache_enabled: bool = True
    cache_backend: str = "sqlite"
    cache_db_path: str = ".cache/market_research.sqlite3"
    cache_ttl_comps_seconds: int = 604800
    cache_ttl_identity_seconds: int = 2592000

    # Pricing defaults: haggle room above FMV and firm-bottom floor below it.
    default_haggle_pct: float = 0.15
    default_floor_pct: float = 0.10

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def chat_call_kwargs(self) -> dict[str, str]:
        """LiteLLM overrides for chat completions (api_base/api_key when set)."""
        return _call_kwargs(self.llm_api_base, self.llm_api_key or self.openai_api_key)

    def vision_call_kwargs(self) -> dict[str, str]:
        """LiteLLM overrides for vision completions.

        Falls back to the chat model's endpoint/key when the vision-specific
        values are blank.
        """
        return _call_kwargs(
            self.vision_api_base or self.llm_api_base,
            self.vision_api_key or self.llm_api_key or self.openai_api_key,
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor; use as a FastAPI dependency or call directly."""
    return Settings()
