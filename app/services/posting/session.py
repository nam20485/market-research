"""Single-request browser session management for the marketplace auto-fill agent.

Everything is scoped to one `async with open_browser_session(...)` block per
`/api/post/fill` request: the `chrome-devtools-mcp` process is spawned,
`--autoConnect`s to the user's already-running Chrome, and the whole session
(process + browser connection) tears down when the block exits. There is no
persistent cross-request session — see docs/fb_marketplace_auto-fill_caf2840d.plan.md's
"Key design correctness" section for why that matters with anyio + stdio transports.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import Settings, get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


def _build_server_params(settings: Settings) -> StdioServerParameters:
    args = ["chrome-devtools-mcp@latest", "--autoConnect", "--channel", settings.chrome_mcp_channel]
    if settings.chrome_mcp_extra_args:
        args.extend(settings.chrome_mcp_extra_args.split())
    return StdioServerParameters(command=settings.chrome_mcp_command, args=args)


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
