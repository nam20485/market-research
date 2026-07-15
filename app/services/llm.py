"""Thin async wrapper around LiteLLM for chat and vision completions."""

from typing import Any

import litellm

from app.config import Settings, get_settings


class LLMService:
    """Wraps LiteLLM's async completion API with the app's model configuration."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> str:
        """Send a text-only chat completion request and return the response text."""
        response = await litellm.acompletion(
            model=model or self._settings.llm_model,
            messages=messages,
            temperature=temperature,
            **kwargs,
        )
        return _extract_text(response)

    async def vision(
        self,
        *,
        text: str,
        image_data_urls: list[str] | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        **kwargs: Any,
    ) -> str:
        """Send a multimodal completion request with text plus optional images.

        `image_data_urls` should be data URLs (e.g. `data:image/jpeg;base64,...`)
        or publicly reachable image URLs, as accepted by LiteLLM's vision models.
        """
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for url in image_data_urls or []:
            content.append({"type": "image_url", "image_url": {"url": url}})

        messages = [{"role": "user", "content": content}]
        response = await litellm.acompletion(
            model=model or self._settings.vision_model,
            messages=messages,
            temperature=temperature,
            **kwargs,
        )
        return _extract_text(response)


def _extract_text(response: Any) -> str:
    """Pull the assistant message text out of a LiteLLM completion response."""
    return response.choices[0].message.content or ""


def get_llm_service() -> LLMService:
    """FastAPI-dependency-friendly factory for `LLMService`."""
    return LLMService()
