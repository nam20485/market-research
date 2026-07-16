"""Tests for `app/services/posting/session.py`'s single-request sessions."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from app.config import Settings
from app.services.posting.profiles import OFFERUP_PROFILE
from app.services.posting.session import (
    _build_appium_env,
    _build_appium_server_params,
    _build_server_params,
    open_appium_session,
    open_browser_session,
    open_session,
)


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


# ── Appium backend ─────────────────────────────────────────────────────────


def test_build_appium_server_params_uses_appium_mcp_command() -> None:
    settings = Settings(appium_mcp_command="npx", appium_mcp_extra_args="")
    params = _build_appium_server_params(settings)
    assert params.command == "npx"
    assert params.args == ["appium-mcp@latest"]


def test_build_appium_server_params_appends_extra_args() -> None:
    settings = Settings(appium_mcp_extra_args="--foo bar")
    params = _build_appium_server_params(settings)
    assert params.args == ["appium-mcp@latest", "--foo", "bar"]


def test_build_appium_env_sets_android_home_and_no_ui() -> None:
    settings = Settings(appium_android_home="/opt/android-sdk")
    env = _build_appium_env(settings)
    assert env["ANDROID_HOME"] == "/opt/android-sdk"
    assert env["NO_UI"] == "true"


def test_build_appium_env_inherits_os_environ() -> None:

    settings = Settings()
    env = _build_appium_env(settings)
    # Parent env keys are preserved (PATH, HOME, etc.).
    assert "PATH" in env
    assert env["NO_UI"] == "true"


async def test_open_appium_session_initializes_selects_device_and_creates_session() -> None:
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
        async with open_appium_session(OFFERUP_PROFILE, Settings()) as session:
            assert session is fake_session

    fake_session.initialize.assert_awaited_once()
    # select_device is called first, then appium_session_management(create)
    assert fake_session.call_tool.await_count == 2
    first_call = fake_session.call_tool.await_args_list[0]
    assert first_call.args[0] == "select_device"
    second_call = fake_session.call_tool.await_args_list[1]
    assert second_call.args[0] == "appium_session_management"
    assert second_call.args[1]["action"] == "create"
    assert second_call.args[1]["platform"] == "android"


# ── open_session dispatch ──────────────────────────────────────────────────


async def test_open_session_dispatches_to_browser_for_chrome_backend() -> None:
    from app.services.posting.profiles import FACEBOOK_MARKETPLACE_PROFILE

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
        async with open_session(FACEBOOK_MARKETPLACE_PROFILE, Settings()) as session:
            assert session is fake_session

    # Browser sessions verify via list_pages (not select_device).
    fake_session.call_tool.assert_awaited_once_with("list_pages", {})


async def test_open_session_dispatches_to_appium_for_appium_backend() -> None:
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
        async with open_session(OFFERUP_PROFILE, Settings()) as session:
            assert session is fake_session

    # Appium sessions call select_device then appium_session_management.
    assert fake_session.call_tool.await_count == 2
