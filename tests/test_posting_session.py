"""Tests for `app/services/posting/session.py`'s single-request browser session."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from app.config import Settings
from app.services.posting.session import _build_server_params, open_browser_session


def test_build_server_params_includes_autoconnect_and_channel() -> None:
    settings = Settings(
        chrome_mcp_command="npx", chrome_mcp_channel="beta", chrome_mcp_extra_args=""
    )
    params = _build_server_params(settings)
    assert params.command == "npx"
    assert params.args == ["chrome-devtools-mcp@latest", "--autoConnect", "--channel", "beta"]


def test_build_server_params_appends_extra_args() -> None:
    settings = Settings(chrome_mcp_channel="stable", chrome_mcp_extra_args="--headless --foo bar")
    params = _build_server_params(settings)
    assert params.args == [
        "chrome-devtools-mcp@latest",
        "--autoConnect",
        "--channel",
        "stable",
        "--headless",
        "--foo",
        "bar",
    ]


async def test_open_browser_session_initializes_and_verifies_via_list_pages() -> None:
    fake_session = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    @asynccontextmanager
    async def _fake_stdio_client(_params: object):
        yield ("read-stream", "write-stream")

    with (
        patch("app.services.posting.session.stdio_client", _fake_stdio_client),
        patch("app.services.posting.session.ClientSession", return_value=fake_session),
    ):
        async with open_browser_session(Settings()) as session:
            assert session is fake_session

    fake_session.initialize.assert_awaited_once()
    fake_session.call_tool.assert_awaited_once_with("list_pages", {})


async def test_open_browser_session_uses_default_settings_when_none_given() -> None:
    fake_session = AsyncMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=False)

    @asynccontextmanager
    async def _fake_stdio_client(_params: object):
        yield ("read-stream", "write-stream")

    with (
        patch("app.services.posting.session.stdio_client", _fake_stdio_client),
        patch("app.services.posting.session.ClientSession", return_value=fake_session),
    ):
        async with open_browser_session() as session:
            assert session is fake_session
