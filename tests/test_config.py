from pathlib import Path

import pytest

from app.config import Settings

_APP_ENV_VARS = (
    "LLM_MODEL",
    "LLM_API_BASE",
    "LLM_API_KEY",
    "VISION_MODEL",
    "VISION_API_BASE",
    "VISION_API_KEY",
    "OPENAI_API_KEY",
    "SEARCH_PROVIDER",
    "TAVILY_API_KEY",
    "CORS_ORIGINS",
    "COMPS_PROVIDER",
    "COMPS_ENABLED",
    "COMPS_MAX_RESULTS",
    "SERPAPI_API_KEY",
    "CACHE_ENABLED",
    "CACHE_BACKEND",
    "CACHE_DB_PATH",
    "CACHE_TTL_COMPS_SECONDS",
    "CACHE_TTL_IDENTITY_SECONDS",
    "DEFAULT_HAGGLE_PCT",
    "DEFAULT_FLOOR_PCT",
)


@pytest.fixture
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Isolate Settings from the repo `.env` file and any ambient app env vars."""
    monkeypatch.chdir(tmp_path)
    for var in _APP_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


@pytest.mark.usefixtures("clean_env")
def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.vision_model == "gpt-4o-mini"
    assert settings.search_provider == "tavily"


@pytest.mark.usefixtures("clean_env")
def test_settings_comps_cache_pricing_defaults() -> None:
    settings = Settings()
    assert settings.comps_provider == "serpapi"
    assert settings.comps_enabled is True
    assert settings.comps_max_results == 8
    assert settings.serpapi_api_key == ""
    assert settings.cache_enabled is True
    assert settings.cache_backend == "sqlite"
    assert settings.cache_db_path == ".cache/market_research.sqlite3"
    assert settings.cache_ttl_comps_seconds == 604800
    assert settings.cache_ttl_identity_seconds == 2592000
    assert settings.default_haggle_pct == 0.15
    assert settings.default_floor_pct == 0.10


def test_settings_reads_comps_cache_pricing_env(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("SERPAPI_API_KEY", "serp-test")
    clean_env.setenv("COMPS_ENABLED", "false")
    clean_env.setenv("COMPS_MAX_RESULTS", "3")
    clean_env.setenv("CACHE_ENABLED", "false")
    clean_env.setenv("CACHE_TTL_COMPS_SECONDS", "60")
    clean_env.setenv("DEFAULT_HAGGLE_PCT", "0.2")
    clean_env.setenv("DEFAULT_FLOOR_PCT", "0.05")

    settings = Settings()

    assert settings.serpapi_api_key == "serp-test"
    assert settings.comps_enabled is False
    assert settings.comps_max_results == 3
    assert settings.cache_enabled is False
    assert settings.cache_ttl_comps_seconds == 60
    assert settings.default_haggle_pct == 0.2
    assert settings.default_floor_pct == 0.05


def test_settings_reads_env(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("OPENAI_API_KEY", "sk-test")
    clean_env.setenv("LLM_MODEL", "gpt-4.1")
    clean_env.setenv("CORS_ORIGINS", "http://a.test, http://b.test")

    settings = Settings()

    assert settings.openai_api_key == "sk-test"
    assert settings.llm_model == "gpt-4.1"
    assert settings.cors_origins_list == ["http://a.test", "http://b.test"]


@pytest.mark.usefixtures("clean_env")
def test_call_kwargs_omit_blanks_by_default() -> None:
    settings = Settings()
    assert settings.chat_call_kwargs() == {}
    assert settings.vision_call_kwargs() == {}


@pytest.mark.usefixtures("clean_env")
def test_vision_inherits_chat_endpoint_and_key() -> None:
    settings = Settings(
        llm_api_base="https://api.cline.bot/api/v1",
        llm_api_key="clp-key",
    )
    expected = {"api_base": "https://api.cline.bot/api/v1", "api_key": "clp-key"}
    assert settings.chat_call_kwargs() == expected
    assert settings.vision_call_kwargs() == expected


@pytest.mark.usefixtures("clean_env")
def test_vision_overrides_and_openai_key_fallback() -> None:
    settings = Settings(
        vision_api_base="https://vision.example/v1",
        vision_api_key="vk",
        openai_api_key="sk-fallback",
    )
    assert settings.chat_call_kwargs() == {"api_key": "sk-fallback"}
    assert settings.vision_call_kwargs() == {
        "api_base": "https://vision.example/v1",
        "api_key": "vk",
    }
