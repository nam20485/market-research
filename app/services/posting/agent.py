"""LiteLLM tool-calling agent loop that fills a marketplace listing form.

Uses the `mcp` SDK's low-level `ClientSession` (passed in by the caller, see
`session.py`) together with LiteLLM's `experimental_mcp_client` helpers to
convert MCP tools to OpenAI tool-calling format and execute tool calls. The
loop never asks the model to submit the listing — profiles instruct it to stop
once the fields are filled (see `app/services/posting/profiles.py`).
"""

import json
from typing import Any, cast

import litellm
from litellm.experimental_mcp_client import call_openai_tool, load_mcp_tools
from litellm.types.utils import ModelResponse
from mcp import ClientSession
from mcp.types import CallToolResult, TextContent
from openai.types.chat import ChatCompletionToolParam

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.prompts.posting import build_posting_system_prompt
from app.services.posting.profiles import MarketplaceProfile

logger = get_logger(__name__)

# Curated subset of chrome-devtools-mcp's tools: enough to navigate, inspect,
# and fill a form, without exposing broader browser-control surface (e.g.
# emulation, network interception) to the agent.
CHROME_CURATED_TOOLS = frozenset(
    {
        "navigate_page",
        "new_page",
        "list_pages",
        "select_page",
        "take_snapshot",
        "take_screenshot",
        "fill",
        "fill_form",
        "click",
        "upload_file",
        "wait_for",
        "handle_dialog",
        "press_key",
    }
)

# Curated subset of appium-mcp's tools: enough to find elements, interact, and
# inspect the screen, without exposing device-kill or uninstall capabilities.
APPIUM_CURATED_TOOLS = frozenset(
    {
        "appium_session_management",
        "appium_find_element",
        "appium_gesture",
        "appium_screenshot",
        "appium_get_page_source",
        "appium_app_lifecycle",
        "appium_context",
        "appium_mobile_device_control",
        "appium_driver_settings",
    }
)

# Alias kept for backward compatibility with existing tests/imports.
CURATED_TOOLS = CHROME_CURATED_TOOLS


def _curated_tools_for(backend: str) -> frozenset[str]:
    """Return the curated tool set for the given MCP backend."""
    if backend == "appium":
        return APPIUM_CURATED_TOOLS
    return CHROME_CURATED_TOOLS


async def fill(
    session: ClientSession,
    profile: MarketplaceProfile,
    *,
    title: str,
    description: str,
    price: float | None,
    image_paths: list[str],
    settings: Settings | None = None,
) -> list[str]:
    """Run the tool-calling fill loop and return a human-readable step summary."""
    settings = settings or get_settings()
    all_tools = cast(
        "list[ChatCompletionToolParam]", await load_mcp_tools(session, format="openai")
    )
    curated = _curated_tools_for(profile.mcp_backend)
    tools = [tool for tool in all_tools if tool["function"]["name"] in curated]
    logger.info(
        "posting: loaded %d/%d curated tools for %s (backend=%s)",
        len(tools),
        len(all_tools),
        profile.id,
        profile.mcp_backend,
    )

    system_prompt = build_posting_system_prompt(
        profile,
        title=title,
        description=description,
        price=price,
        image_paths=image_paths,
    )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    model = settings.posting_model or settings.llm_model
    call_kwargs = settings.chat_call_kwargs()
    steps: list[str] = []

    for step in range(settings.posting_max_steps):
        response = cast(
            ModelResponse,
            await litellm.acompletion(
                model=model,
                messages=messages,
                tools=tools,
                temperature=0.1,
                api_base=call_kwargs.get("api_base"),
                api_key=call_kwargs.get("api_key"),
            ),
        )
        message = response.choices[0].message
        tool_calls = message.tool_calls or []
        messages.append(message.model_dump())

        if not tool_calls:
            steps.append(message.content or "Agent finished without further tool calls.")
            logger.info("posting: fill loop stopped after %d step(s)", step + 1)
            break

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            logger.info("posting: calling tool %s", tool_name)
            result = await call_openai_tool(session, tool_call)
            steps.append(f"{tool_name}: {'error' if result.isError else 'ok'}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": _tool_result_text(result),
                }
            )
    else:
        steps.append(f"Stopped after reaching posting_max_steps={settings.posting_max_steps}.")
        logger.warning("posting: fill loop hit posting_max_steps=%d", settings.posting_max_steps)

    return steps


def _tool_result_text(result: CallToolResult) -> str:
    """Flatten an MCP tool result's text content blocks into a single string."""
    texts = [block.text for block in result.content if isinstance(block, TextContent)]
    text = "\n".join(texts)
    return text or json.dumps({"isError": result.isError})
