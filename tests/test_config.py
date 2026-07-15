import pytest

from app.config import Settings


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.vision_model == "gpt-4o-mini"
    assert settings.search_provider == "tavily"


def test_settings_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")

    settings = Settings()

    assert settings.openai_api_key == "sk-test"
    assert settings.llm_model == "gpt-4.1"
    assert settings.cors_origins_list == ["http://a.test", "http://b.test"]
