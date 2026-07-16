"""Thin async wrapper around LiteLLM / OpenAI-compatible HTTP for chat and vision."""

import time
from typing import Any

import httpx
import litellm

from app.config import Settings, get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# LiteLLM routing prefix for generic OpenAI-compatible endpoints. When we call a
# custom api_base ourselves we strip this so the upstream sees its own model id
# (e.g. Cline's "cline-pass/qwen3.7-plus").
_OPENAI_ROUTING_PREFIX = "openai/"


class LLMService:
    """Chat + vision completions using LiteLLM or a custom OpenAI-compatible base."""

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
        return await self._complete(
            model=model or self._settings.llm_model,
            messages=messages,
            temperature=temperature,
            call_kwargs=self._settings.chat_call_kwargs(),
            **kwargs,
        )

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
        or publicly reachable image URLs, as accepted by OpenAI-style vision models.
        """
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for url in image_data_urls or []:
            content.append({"type": "image_url", "image_url": {"url": url}})

        messages = [{"role": "user", "content": content}]
        return await self._complete(
            model=model or self._settings.vision_model,
            messages=messages,
            temperature=temperature,
            call_kwargs=self._settings.vision_call_kwargs(),
            **kwargs,
        )

    async def _complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        call_kwargs: dict[str, str],
        **kwargs: Any,
    ) -> str:
        api_base = call_kwargs.get("api_base")
        started = time.perf_counter()
        via = "openai-compatible" if api_base else "litellm"
        logger.info("llm %s start: model=%s messages=%d", via, model, len(messages))
        try:
            if api_base:
                text = await _openai_compatible_completion(
                    api_base=api_base,
                    api_key=call_kwargs.get("api_key", ""),
                    model=_strip_openai_routing_prefix(model),
                    messages=messages,
                    temperature=temperature,
                    **kwargs,
                )
            else:
                response = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    **call_kwargs,
                    **kwargs,
                )
                text = _extract_litellm_text(response)
        except Exception:
            logger.exception(
                "llm %s failed after %.2fs: model=%s",
                via,
                time.perf_counter() - started,
                model,
            )
            raise
        logger.info(
            "llm %s complete in %.2fs: model=%s response_len=%d",
            via,
            time.perf_counter() - started,
            model,
            len(text),
        )
        return text


def _strip_openai_routing_prefix(model: str) -> str:
    """Drop LiteLLM's `openai/` routing prefix when talking to a custom api_base."""
    if model.startswith(_OPENAI_ROUTING_PREFIX):
        return model[len(_OPENAI_ROUTING_PREFIX) :]
    return model


def _unwrap_openai_compatible_body(body: dict[str, Any]) -> dict[str, Any]:
    """Normalize providers that wrap the OpenAI payload (e.g. Cline `{data, success}`)."""
    if "choices" in body:
        return body
    data = body.get("data")
    if isinstance(data, dict) and "choices" in data:
        return data
    raise ValueError(
        "OpenAI-compatible response missing choices "
        f"(top-level keys: {sorted(body.keys())})"
    )


async def _openai_compatible_completion(
    *,
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    temperature: float,
    **kwargs: Any,
) -> str:
    """POST /chat/completions to a custom OpenAI-compatible endpoint."""
    url = api_base.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        **kwargs,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()

    completion = _unwrap_openai_compatible_body(body)
    choices = completion.get("choices") or []
    if not choices:
        raise ValueError("OpenAI-compatible response has empty choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    return content or ""


def _extract_litellm_text(response: Any) -> str:
    """Pull the assistant message text out of a LiteLLM completion response."""
    return response.choices[0].message.content or ""


def get_llm_service() -> LLMService:
    """FastAPI-dependency-friendly factory for `LLMService`."""
    return LLMService()
