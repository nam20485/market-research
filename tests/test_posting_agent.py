"""Agent fill-loop unit tests: a fake `ClientSession` plus patched LiteLLM/MCP calls."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

from mcp import ClientSession
from mcp.types import CallToolResult, TextContent

from app.config import Settings
from app.services.posting.agent import (
    APPIUM_CURATED_TOOLS,
    CURATED_TOOLS,
    fill,
)
from app.services.posting.profiles import FACEBOOK_MARKETPLACE_PROFILE, OFFERUP_PROFILE

_ALL_OPENAI_TOOLS = [
    {"type": "function", "function": {"name": "fill", "parameters": {}}},
    {"type": "function", "function": {"name": "take_snapshot", "parameters": {}}},
    # Not in CURATED_TOOLS; must be filtered out before being handed to the model.
    {"type": "function", "function": {"name": "emulate_network", "parameters": {}}},
]

_ALL_OPENAI_TOOLS_APPIUM = [
    {"type": "function", "function": {"name": "appium_gesture", "parameters": {}}},
    {"type": "function", "function": {"name": "appium_screenshot", "parameters": {}}},
    # Not in APPIUM_CURATED_TOOLS; must be filtered out.
    {"type": "function", "function": {"name": "appium_uninstall_app", "parameters": {}}},
]


def _fake_tool_call(call_id: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments="{}"))


def _fake_message(*, content: str | None = None, tool_calls: list | None = None) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=tool_calls or [])
    message.model_dump = lambda: {  # noqa: E731 - tiny test double
        "role": "assistant",
        "content": message.content,
        "tool_calls": message.tool_calls,
    }
    return message


def _fake_response(message: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _fake_session() -> ClientSession:
    """An opaque token stood in for a real `ClientSession` (never dereferenced)."""
    return cast(ClientSession, object())


async def test_fill_loop_calls_tool_then_stops_on_final_message() -> None:
    session = _fake_session()
    tool_call = _fake_tool_call("call-1", "fill")
    first_response = _fake_response(_fake_message(tool_calls=[tool_call]))
    second_response = _fake_response(_fake_message(content="All fields filled."))

    tool_result = CallToolResult(
        content=[TextContent(type="text", text="filled title+description")], isError=False
    )

    with (
        patch(
            "app.services.posting.agent.load_mcp_tools",
            AsyncMock(return_value=_ALL_OPENAI_TOOLS),
        ),
        patch(
            "app.services.posting.agent.litellm.acompletion",
            AsyncMock(side_effect=[first_response, second_response]),
        ) as mock_acompletion,
        patch(
            "app.services.posting.agent.call_openai_tool",
            AsyncMock(return_value=tool_result),
        ) as mock_call_tool,
    ):
        steps = await fill(
            session,
            FACEBOOK_MARKETPLACE_PROFILE,
            title="Lamp",
            description="Great lamp",
            price=25.0,
            image_paths=["/tmp/lamp.jpg"],
            settings=Settings(posting_max_steps=5),
        )

    assert steps == ["fill: ok", "All fields filled."]
    assert mock_acompletion.await_count == 2
    mock_call_tool.assert_awaited_once_with(session, tool_call)

    # Only curated tools are handed to the model.
    _, first_call_kwargs = mock_acompletion.await_args_list[0]
    tool_names = {tool["function"]["name"] for tool in first_call_kwargs["tools"]}
    assert tool_names == {"fill", "take_snapshot"}
    assert tool_names.issubset(CURATED_TOOLS)

    # The tool result gets folded back into the message history for the next turn.
    _, second_call_kwargs = mock_acompletion.await_args_list[1]
    tool_messages = [m for m in second_call_kwargs["messages"] if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert tool_messages[0]["tool_call_id"] == "call-1"
    assert "filled title+description" in tool_messages[0]["content"]


async def test_fill_loop_stops_after_max_steps_when_model_never_finishes() -> None:
    tool_call = _fake_tool_call("call-x", "fill")
    always_calling_response = _fake_response(_fake_message(tool_calls=[tool_call]))
    tool_result = CallToolResult(content=[TextContent(type="text", text="ok")], isError=False)

    with (
        patch(
            "app.services.posting.agent.load_mcp_tools",
            AsyncMock(return_value=_ALL_OPENAI_TOOLS),
        ),
        patch(
            "app.services.posting.agent.litellm.acompletion",
            AsyncMock(return_value=always_calling_response),
        ) as mock_acompletion,
        patch(
            "app.services.posting.agent.call_openai_tool",
            AsyncMock(return_value=tool_result),
        ),
    ):
        steps = await fill(
            _fake_session(),
            FACEBOOK_MARKETPLACE_PROFILE,
            title="Lamp",
            description="Great lamp",
            price=None,
            image_paths=[],
            settings=Settings(posting_max_steps=3),
        )

    assert mock_acompletion.await_count == 3
    assert steps[-1] == "Stopped after reaching posting_max_steps=3."


async def test_fill_loop_records_error_tool_results() -> None:
    tool_call = _fake_tool_call("call-err", "fill")
    first_response = _fake_response(_fake_message(tool_calls=[tool_call]))
    second_response = _fake_response(_fake_message(content="Done despite the error."))
    error_result = CallToolResult(content=[], isError=True)

    with (
        patch(
            "app.services.posting.agent.load_mcp_tools",
            AsyncMock(return_value=_ALL_OPENAI_TOOLS),
        ),
        patch(
            "app.services.posting.agent.litellm.acompletion",
            AsyncMock(side_effect=[first_response, second_response]),
        ),
        patch(
            "app.services.posting.agent.call_openai_tool",
            AsyncMock(return_value=error_result),
        ),
    ):
        steps = await fill(
            _fake_session(),
            FACEBOOK_MARKETPLACE_PROFILE,
            title="Lamp",
            description="Great lamp",
            price=None,
            image_paths=[],
            settings=Settings(posting_max_steps=5),
        )

    assert steps[0] == "fill: error"
    assert steps[1] == "Done despite the error."


async def test_fill_loop_uses_appium_curated_tools_for_offerup() -> None:
    session = _fake_session()
    tool_call = _fake_tool_call("call-1", "appium_gesture")
    first_response = _fake_response(_fake_message(tool_calls=[tool_call]))
    second_response = _fake_response(_fake_message(content="All fields filled."))

    tool_result = CallToolResult(
        content=[TextContent(type="text", text="tapped sell button")], isError=False
    )

    with (
        patch(
            "app.services.posting.agent.load_mcp_tools",
            AsyncMock(return_value=_ALL_OPENAI_TOOLS_APPIUM),
        ),
        patch(
            "app.services.posting.agent.litellm.acompletion",
            AsyncMock(side_effect=[first_response, second_response]),
        ) as mock_acompletion,
        patch(
            "app.services.posting.agent.call_openai_tool",
            AsyncMock(return_value=tool_result),
        ),
    ):
        steps = await fill(
            session,
            OFFERUP_PROFILE,
            title="Couch",
            description="Great couch",
            price=100.0,
            image_paths=["/tmp/couch.jpg"],
            settings=Settings(posting_max_steps=5),
        )

    assert steps == ["appium_gesture: ok", "All fields filled."]

    # Only appium curated tools are handed to the model — non-curated ones are filtered out.
    _, first_call_kwargs = mock_acompletion.await_args_list[0]
    tool_names = {tool["function"]["name"] for tool in first_call_kwargs["tools"]}
    assert tool_names == {"appium_gesture", "appium_screenshot"}
    assert tool_names.issubset(APPIUM_CURATED_TOOLS)
