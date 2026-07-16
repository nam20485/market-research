"""Single-request session management for the marketplace auto-fill agent.

Everything is scoped to one `async with open_session(...)` block per
`/api/post/fill` request. Depending on the profile's `mcp_backend`, either
`chrome-devtools-mcp` (desktop browser) or `appium-mcp` (Android app) is
spawned, connected, and the whole session tears down when the block exits.
There is no persistent cross-request session — see
docs/fb_marketplace_auto-fill_caf2840d.plan.md's "Key design correctness"
section for why that matters with anyio + stdio transports.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.services.posting.profiles import MarketplaceProfile

logger = get_logger(__name__)


def _build_server_params(settings: Settings) -> StdioServerParameters:
    args = ["chrome-devtools-mcp@latest", "--autoConnect", "--channel", settings.chrome_mcp_channel]
    if settings.chrome_mcp_extra_args:
        args.extend(settings.chrome_mcp_extra_args.split())
    return StdioServerParameters(command=settings.chrome_mcp_command, args=args)


def _build_appium_env(settings: Settings) -> dict[str, str]:
    """Build the environment for the appium-mcp subprocess.

    Inherits the parent environment so PATH/HOME/etc. remain available, then
    adds ANDROID_HOME (when configured) and forces NO_UI mode for faster,
    lower-token tool responses in the agent loop.
    """
    env = dict(os.environ)
    if settings.appium_android_home:
        env["ANDROID_HOME"] = settings.appium_android_home
    env["NO_UI"] = "true"
    return env


def _build_appium_server_params(settings: Settings) -> StdioServerParameters:
    args = ["appium-mcp@latest"]
    if settings.appium_mcp_extra_args:
        args.extend(settings.appium_mcp_extra_args.split())
    return StdioServerParameters(
        command=settings.appium_mcp_command,
        args=args,
        env=_build_appium_env(settings),
    )


@asynccontextmanager
async def open_browser_session(settings: Settings | None = None) -> AsyncIterator[ClientSession]:
    """Spawn `chrome-devtools-mcp`, connect to the user's Chrome, and yield a live session.

    Verifies the connection actually reached a browser by calling the
    `list_pages` tool once after `initialize()`. Everything is closed when the
    caller's `async with` block exits.
    """
    settings = settings or get_settings()
    params = _build_server_params(settings)
    logger.info(
        "posting: spawning %s %s", settings.chrome_mcp_command, " ".join(params.args)
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            await session.call_tool("list_pages", {})
            logger.info("posting: mcp session initialized and verified via list_pages")
            yield session


@asynccontextmanager
async def open_appium_session(
    profile: MarketplaceProfile,
    settings: Settings | None = None,
) -> AsyncIterator[ClientSession]:
    """Spawn `appium-mcp`, create an Android session, and yield a live session.

    Selects the target device (auto-selects if only one emulator is running),
    then creates an Android session targeting the profile's app package. The
    agent loop drives the app from there. Everything is closed when the
    caller's `async with` block exits.
    """
    settings = settings or get_settings()
    params = _build_appium_server_params(settings)
    logger.info(
        "posting: spawning %s %s", settings.appium_mcp_command, " ".join(params.args)
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            # Select the target device — auto-selects when only one is found.
            await session.call_tool("select_device", {})
            # Create an Android session targeting the marketplace app.
            create_args: dict[str, object] = {"action": "create", "platform": "android"}
            if profile.app_package:
                create_args["capabilities"] = {"appium:appPackage": profile.app_package}
            await session.call_tool("appium_session_management", create_args)
            logger.info("posting: appium session initialized for %s", profile.id)
            yield session


@asynccontextmanager
async def open_session(
    profile: MarketplaceProfile,
    settings: Settings | None = None,
) -> AsyncIterator[ClientSession]:
    """Dispatch to the correct MCP backend session based on the profile.

    ``chrome-devtools`` profiles use ``open_browser_session``; ``appium``
    profiles use ``open_appium_session``.
    """
    if profile.mcp_backend == "appium":
        async with open_appium_session(profile, settings) as session:
            yield session
    else:
        async with open_browser_session(settings) as session:
            yield session
