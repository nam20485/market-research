---
name: FB Marketplace auto-fill
overview: "Add a local-only, marketplace-agnostic \"auto-fill\" feature: from the final Listing step, connect to the user's existing Chrome via chrome-devtools-mcp (--autoConnect) and use a LiteLLM tool-calling agent loop to fill a Facebook Marketplace create-item form (title, description, images), stopping before Publish so the user submits."
todos:
  - id: deps-config
    content: Add mcp dependency to pyproject.toml and posting config fields (posting_enabled, chrome_mcp_command/channel/extra_args, posting_model, posting_max_steps) to app/config.py
    status: pending
  - id: profiles-schemas-prompts
    content: Create app/services/posting/profiles.py (MarketplaceProfile + registry with FB profile), app/schemas/posting.py, and app/prompts/posting.py (system prompt builder, fill-only)
    status: pending
  - id: browser-agent-engine
    content: Implement app/services/posting/session.py (open_browser_session async context manager that spawns chrome-devtools-mcp over stdio + autoConnect and yields a ClientSession, scoped to one request) and app/services/posting/agent.py (LiteLLM tool-calling fill loop using load_mcp_tools/call_openai_tool with that session, curated toolset)
    status: pending
  - id: posting-api
    content: Add app/api/posting.py (GET /api/post/capabilities, single POST /api/post/fill multipart+temp images that connects+fills+tears down in one request) and mount router in app/main.py
    status: pending
  - id: frontend-photos-api
    content: Lift accumulated photos to App state via IdentifyStep onLocked and pass to ListingStep; add getPostingCapabilities + fillMarketplaceListing to frontend/src/api.js
    status: pending
  - id: frontend-dialog
    content: Add Post-to-FB button in ListingStep FB card and build PostToMarketplaceDialog.jsx implementing the readiness-confirm -> single fill call -> review-and-publish flow
    status: pending
  - id: docs
    content: Document local-only usage, Node/Chrome 144 beta prerequisites, chrome://inspect remote-debugging setup, and POSTING_ENABLED in .env.example, AGENTS.md, README
    status: pending
  - id: tests
    content: Add backend tests (profiles, prompts, endpoints with mocked session/agent, agent loop) and frontend tests (dialog steps, button visibility, api functions, photo passthrough); run scripts/validate.ps1 -All
    status: pending
isProject: false
---

# FB Marketplace Auto-Fill (agentic, local-only)

## Approach & constraints (confirmed)

- Keep LiteLLM (no library swap). Agentic fill: LiteLLM `experimental_mcp_client` + `chrome-devtools-mcp` tool-calling loop, driven by a per-marketplace "posting profile" (marketplace-agnostic; FB is the first profile).
- Single-request design: connect + fill + teardown happen inside ONE backend request/asyncio task. No persistent cross-request session, no `AsyncExitStack` singleton. UX gate ("Chrome open & logged in? Click OK") happens BEFORE the single call.
- Local-only: the FastAPI backend must run locally (`uv run`/compose) with Node/`npx` + Chrome 144+. It spawns the MCP server and connects to the user's Chrome via `--autoConnect --channel beta`. Does not work against Cloud Run.
- Fill-only: the agent must never click Publish/Post; it fills and stops for the user to submit.
- Phase 1 fields: title, description, images (price optional, prefilled from research; category/condition left to the user).

## Key design correctness

- Do NOT use LiteLLM's high-level `MCPClient.run_with_session` (it re-opens the stdio transport per call, spawning a new MCP process + browser connection each time). Instead, open ONE session with the `mcp` SDK inside the fill request via `async with stdio_client(params) as (r, w): async with ClientSession(r, w) as session:`, and pass that `session` into `load_mcp_tools(session=...)` / `call_openai_tool(session=...)`.
- Because everything is scoped to a single request/task, the anyio "connect and cleanup on the same task" constraint is satisfied automatically, and Chrome's autoConnect permission dialog is triggered once per fill.
- The fill loop can run for a while (multiple LLM round-trips); set a generous request timeout and bound it with `posting_max_steps`.

## Backend

New package `app/services/posting/`:
- `profiles.py` - `MarketplaceProfile` (id, label, `create_url`, `fill_instructions`, `field_hints`) + a registry. FB profile: `create_url = https://www.facebook.com/marketplace/create/item`, instructions mapping title/description/photos, and an explicit "do NOT click Publish" rule.
- `session.py` - `open_browser_session(settings)` async context manager: builds `StdioServerParameters` for `chrome-devtools-mcp` (`--autoConnect --channel beta` + extra args), enters `stdio_client` + `ClientSession`, `initialize()`s, verifies via `list_pages`, and yields the live `ClientSession`. Everything closes on context exit (end of request).
- `agent.py` - `fill(session, profile, content, image_paths, settings)`: `load_mcp_tools(session, format="openai")` filtered to a curated toolset (`navigate_page, new_page, list_pages, select_page, take_snapshot, take_screenshot, fill, fill_form, click, upload_file, wait_for, handle_dialog, press_key`), build system prompt from profile + listing + local image paths, loop `litellm.acompletion(model=..., tools=..., **settings.chat_call_kwargs())` → `call_openai_tool(session, openai_tool)` until the model reports done or `posting_max_steps`.

New `app/prompts/posting.py` - `build_posting_system_prompt(profile, title, description, price, image_paths)`.

New `app/schemas/posting.py` - `MarketplaceInfo`, `PostingCapabilities`, `FillResponse` (the FillRequest arrives as multipart form so images can be attached).

New `app/api/posting.py` (mounted at `/api` in [app/main.py](app/main.py)):
- `GET /api/post/capabilities` -> `{enabled, marketplaces:[{id,label}]}` (driven by a `POSTING_ENABLED` flag; lets the frontend hide the button when pointed at Cloud Run).
- `POST /api/post/fill` (multipart: `marketplace`, `title`, `description`, `price?`, `images[]`) -> write images to a temp dir, then in one request: `async with open_browser_session(...) as session: await fill(session, ...)`; return `{status, steps_summary, screenshot?}`. Temp images cleaned up in a `finally`.

Config additions in [app/config.py](app/config.py): `posting_enabled: bool = True`, `chrome_mcp_command: str = "npx"`, `chrome_mcp_channel: str = "beta"`, `chrome_mcp_extra_args: str = ""`, `posting_model: str = ""` (falls back to `llm_model`), `posting_max_steps: int = 40`.

Dependency: add `mcp>=1.0` to `[project].dependencies` in [pyproject.toml](pyproject.toml) (LiteLLM's MCP helpers require it). Node/`npx` is a runtime prerequisite (documented, not vendored).

## Frontend

- Lift photos to App state: [frontend/src/components/IdentifyStep.jsx](frontend/src/components/IdentifyStep.jsx) already keeps files in `turns[].images`; pass the accumulated `File[]` up through `onLocked` and store `photos` in [frontend/src/App.jsx](frontend/src/App.jsx), then pass `photos` into `ListingStep`.
- New API functions in [frontend/src/api.js](frontend/src/api.js): `getPostingCapabilities()` and `fillMarketplaceListing({marketplace, listing, price, images})` (multipart), following the existing `parseJsonOrThrow` pattern.
- Add a "Post to Facebook Marketplace" button on the Facebook `ListingCard` header in [frontend/src/components/ListingStep.jsx](frontend/src/components/ListingStep.jsx) (only when capabilities.enabled and marketplace is FB).
- New `frontend/src/components/PostToMarketplaceDialog.jsx` modal (built from scratch with existing Tailwind patterns; `role="dialog"`, dark-mode variants) implementing the simplified flow: (1) readiness instructions ("Open Chrome, log into Facebook, enable remote debugging once at chrome://inspect/#remote-debugging") + optional price field prefilled from research + OK/Cancel, (2) OK -> single `fillMarketplaceListing(...)` call with a progress indicator (connect+fill happen server-side, Chrome shows its Allow dialog), (3) success -> message telling the user to review in Chrome and click Publish themselves; errors offer retry.

## Docs

Update [.env.example](.env.example), [AGENTS.md](AGENTS.md), and README: local-only nature, Node/`npx` + Chrome 144 beta prerequisites, `chrome://inspect/#remote-debugging` one-time setup, autoConnect permission dialog, `POSTING_ENABLED`.

## Testing (keep CI gates green; frontend >=95%)

- Backend (`tests/`): profile registry, prompt builder, temp-image handling, the `/fill` endpoint with `open_browser_session` + `fill` mocked via `app.dependency_overrides` / monkeypatch; agent loop unit-tested with a fake `session` + patched `litellm.acompletion` and `call_openai_tool`.
- Frontend: `PostToMarketplaceDialog` tests (readiness -> fill -> success, Cancel, error/retry), `ListingStep` button visibility, `api.test.js` for new functions, `App.test.jsx` photo passthrough. Mock `../api.js`.
- Run `pwsh -NoProfile -File ./scripts/validate.ps1 -All`.

## Phase 2 note (OfferUp)

The `MarketplaceProfile` abstraction makes OfferUp a future profile. Chrome mobile emulation (viewport/touch/UA via `resize_page`/`emulate`) only renders OfferUp's limited mobile web, not the native app; posting support needs verification, with a real Android emulator + Appium as a heavier fallback outside MCP scope.

## Risks

- Long-running single request: the fill loop makes several LLM round-trips + tool calls, so the `/fill` request can take a while. Mitigate with a generous timeout and `posting_max_steps`; the frontend shows a progress indicator.
- FB DOM/anti-automation variability; mitigated by the agentic (snapshot-driven) approach and fill-only scope.
- Requires a tool-calling-capable chat model (default `gpt-4o-mini` is fine; a non-tool-calling ZAI model would need `POSTING_MODEL` set to a capable one).