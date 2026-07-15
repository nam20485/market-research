from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import Settings
from app.services.llm import (
    LLMService,
    _strip_openai_routing_prefix,
    _unwrap_openai_compatible_body,
)

_APP_ENV_VARS = (
    "LLM_MODEL",
    "LLM_API_BASE",
    "LLM_API_KEY",
    "VISION_MODEL",
    "VISION_API_BASE",
    "VISION_API_KEY",
    "OPENAI_API_KEY",
)


@pytest.fixture
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate Settings from the repo `.env` and ambient LLM env vars."""
    monkeypatch.chdir(tmp_path)
    for var in _APP_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _fake_completion_response(text: str) -> SimpleNamespace:
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.mark.usefixtures("clean_env")
async def test_chat_calls_litellm_with_configured_model() -> None:
    settings = Settings(llm_model="gpt-test")
    service = LLMService(settings)

    with patch(
        "app.services.llm.litellm.acompletion",
        new=AsyncMock(return_value=_fake_completion_response("hello")),
    ) as mock_completion:
        result = await service.chat([{"role": "user", "content": "hi"}])

    assert result == "hello"
    mock_completion.assert_awaited_once()
    _, kwargs = mock_completion.call_args
    assert kwargs["model"] == "gpt-test"


@pytest.mark.usefixtures("clean_env")
async def test_vision_includes_image_content_parts() -> None:
    settings = Settings(vision_model="vision-test")
    service = LLMService(settings)

    with patch(
        "app.services.llm.litellm.acompletion",
        new=AsyncMock(return_value=_fake_completion_response('{"ok": true}')),
    ) as mock_completion:
        result = await service.vision(
            text="describe this", image_data_urls=["data:image/jpeg;base64,abc"]
        )

    assert result == '{"ok": true}'
    _, kwargs = mock_completion.call_args
    assert kwargs["model"] == "vision-test"
    content = kwargs["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "describe this"}
    assert content[1] == {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,abc"}}


def test_strip_openai_routing_prefix() -> None:
    assert _strip_openai_routing_prefix("openai/cline-pass/qwen3.7-plus") == (
        "cline-pass/qwen3.7-plus"
    )
    assert _strip_openai_routing_prefix("zai/glm-4.7") == "zai/glm-4.7"


def test_unwrap_cline_envelope() -> None:
    unwrapped = _unwrap_openai_compatible_body(
        {"success": True, "data": {"choices": [{"message": {"content": "OK"}}]}}
    )
    assert unwrapped["choices"][0]["message"]["content"] == "OK"


def test_unwrap_standard_openai_body() -> None:
    body = {"choices": [{"message": {"content": "hi"}}]}
    assert _unwrap_openai_compatible_body(body) is body


@pytest.mark.usefixtures("clean_env")
async def test_custom_api_base_uses_http_and_unwraps_envelope() -> None:
    settings = Settings(
        llm_model="openai/cline-pass/qwen3.7-plus",
        llm_api_base="https://api.cline.bot/api/v1",
        llm_api_key="test-key",
    )
    service = LLMService(settings)

    fake_response = httpx.Response(
        200,
        json={"success": True, "data": {"choices": [{"message": {"content": "OK"}}]}},
        request=httpx.Request("POST", "https://api.cline.bot/api/v1/chat/completions"),
    )

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=fake_response)

    with (
        patch("app.services.llm.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.llm.litellm.acompletion", new=AsyncMock()) as mock_litellm,
    ):
        result = await service.chat([{"role": "user", "content": "hi"}])

    assert result == "OK"
    mock_litellm.assert_not_awaited()
    mock_client.post.assert_awaited_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "https://api.cline.bot/api/v1/chat/completions"
    assert kwargs["json"]["model"] == "cline-pass/qwen3.7-plus"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"


@pytest.mark.usefixtures("clean_env")
async def test_custom_api_base_raises_on_http_error() -> None:
    settings = Settings(
        llm_model="openai/cline-pass/qwen3.7-plus",
        llm_api_base="https://api.cline.bot/api/v1",
        llm_api_key="test-key",
    )
    service = LLMService(settings)

    fake_response = httpx.Response(
        400,
        json={"error": "invalid model format", "success": False},
        request=httpx.Request("POST", "https://api.cline.bot/api/v1/chat/completions"),
    )
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=fake_response)

    with (
        patch("app.services.llm.httpx.AsyncClient", return_value=mock_client),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await service.chat([{"role": "user", "content": "hi"}])
