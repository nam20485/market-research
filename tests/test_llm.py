from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.config import Settings
from app.services.llm import LLMService


def _fake_completion_response(text: str) -> SimpleNamespace:
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


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
