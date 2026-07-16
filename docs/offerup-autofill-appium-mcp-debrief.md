# OfferUp Auto-Fill (Appium MCP) — Post-Implementation Debrief

**Date:** 2026-07-15
**Plan:** [`docs/offerup-autofill-appium-mcp.md`](offerup-autofill-appium-mcp.md)
**Original plan (planning session):** [`.kilo/plans/1784168648160-offerup-autofill-appium-mcp.md`](../.kilo/plans/1784168648160-offerup-autofill-appium-mcp.md)

---

## Goal

Extend the existing marketplace auto-fill system (built for Facebook Marketplace
via `chrome-devtools-mcp`) to support OfferUp, which is **mobile-only** — it has
no web posting flow. The chosen approach was Appium MCP (`appium-mcp`) driving
an Android emulator running the real OfferUp app, preserving the marketplace-
agnostic architecture.

## Decision Recap

Four options were evaluated:

| Option | Verdict | Reason |
|--------|---------|--------|
| A. Chrome mobile emulation (CDP) | Rejected | OfferUp's mobile web has no posting UI |
| **B. Appium MCP + Android emulator** | **Chosen** | Same MCP protocol, reuses agent loop, drives real app |
| C. Direct Appium WebDriver (no MCP) | Rejected | Breaks architecture; parallel fill loop needed |
| D. Reverse-engineered OfferUp API | Rejected | Fragile, ToS/legal risk |

## What Was Implemented

### Backend (6 files, 4 commits)

| File | Change |
|------|--------|
| `app/services/posting/profiles.py` | Added `mcp_backend` and `app_package` fields to `MarketplaceProfile`; registered `OFFERUP_PROFILE` (`mcp_backend="appium"`, `app_package="com.offerup"`); added `BACKEND_CHROME_DEVTOOLS`/`BACKEND_APPIUM` constants; set explicit `mcp_backend` on FB profile |
| `app/services/posting/agent.py` | Added `APPIUM_CURATED_TOOLS` frozenset (`appium_find_element`, `appium_gesture`, `appium_screenshot`, `appium_get_page_source`, `appium_app_lifecycle`, `appium_context`, `appium_mobile_device_control`, `appium_driver_settings`, `appium_session_management`); `fill()` now selects curated tools via `_curated_tools_for(backend)`; kept `CURATED_TOOLS` alias for backward compat |
| `app/services/posting/session.py` | Added `_build_appium_env()` (inherits `os.environ`, injects `ANDROID_HOME` + `NO_UI=true`), `_build_appium_server_params()`, `open_appium_session()` (spawns `appium-mcp@latest`, calls `select_device` then `appium_session_management(create)`), and `open_session()` dispatch wrapper |
| `app/prompts/posting.py` | Template now uses `{role}`, `{tool_noun}`, `{inspect_hint}`, `{target_line}` placeholders; `build_posting_system_prompt()` branches on `mcp_backend` → "mobile-app automation agent" + "App package: com.offerup" vs "browser-automation agent" + "Create-listing URL:" |
| `app/config.py` | Added `appium_mcp_command` (`npx`), `appium_mcp_extra_args`, `appium_android_home`, `appium_emulator_name` |
| `app/api/posting.py` | Switched from `open_browser_session(settings)` to `open_session(profile, settings)` dispatch; added `_backend_error_message()` returning Chrome vs emulator troubleshooting hints for 502 responses |

### Frontend (2 files)

| File | Change |
|------|--------|
| `frontend/src/components/ListingStep.jsx` | Added `OFFERUP_ID` constant, `showOfferupDialog` state, `canPostToOfferup` gate, "Post to OfferUp" button on OfferUp card `headerExtra`, and OfferUp dialog render block |
| `frontend/src/components/PostToMarketplaceDialog.jsx` | Added `MARKETPLACE_CONFIG` map driving per-marketplace title, readiness instructions (Chrome/emulator), filling text, and success copy; `aria-label` and `<h3>` now dynamic; readiness items support both plain strings and `{html}` objects (for `<code>` rendering) |

### Docs (2 files)

| File | Change |
|------|--------|
| `.env.example` | Restructured posting section into a unified block documenting both Chrome and Appium backends; added `APPIUM_MCP_COMMAND`, `APPIUM_MCP_EXTRA_ARGS`, `APPIUM_ANDROID_HOME`, `APPIUM_EMULATOR_NAME` |
| `AGENTS.md` | Expanded the marketplace auto-fill learned-fact to document both backends, the `open_session` dispatch, per-backend curated tools, and per-marketplace readiness instructions |

### Tests (6 files, +280 lines)

| File | New tests |
|------|-----------|
| `tests/test_posting.py` | OfferUp profile registry lookup, OfferUp in `list_profiles`, OfferUp prompt (mobile-app wording + `app_package`), FB prompt (browser wording), OfferUp happy-path `/fill`, OfferUp 502 (emulator error), OfferUp in capabilities response |
| `tests/test_posting_agent.py` | Appium backend uses `APPIUM_CURATED_TOOLS` (non-curated tools filtered out) |
| `tests/test_posting_session.py` | `_build_appium_server_params` (command + extra args), `_build_appium_env` (ANDROID_HOME + NO_UI + PATH inheritance), `open_appium_session` (select_device + session_management calls), `open_session` dispatch (Chrome → list_pages, Appium → select_device + create) |
| `tests/test_config.py` | Appium config defaults + env var round-trip |
| `ListingStep.test.jsx` | OfferUp button hidden when disabled, OfferUp button shown + dialog opens with emulator instructions + closes |
| `PostToMarketplaceDialog.test.jsx` | OfferUp-specific title + emulator readiness instructions, FB-specific title + Chrome readiness instructions |

## Validation Results

| Gate | Result |
|------|--------|
| `uv run pytest` (backend) | **135 passed**, 0 failed |
| `uv run ruff check .` (lint) | **All checks passed** |
| `uv run basedpyright` (typecheck) | **0 errors, 0 warnings, 0 notes** |
| `pnpm test` (frontend) | **106 passed**, 0 failed |
| Frontend coverage | **98.58%** statements (≥95% threshold met) |
| `pnpm build` (production build) | **Built successfully** |

## Plan vs Implementation: Deviations

| Plan item | What happened | Why |
|-----------|---------------|-----|
| Config field `APPIUM_OFFERUP_PACKAGE` | **Not added as a separate Settings field** | The app package is encoded in the `OFFERUP_PROFILE` dataclass (`app_package="com.offerup"`) rather than as an env var. It's a profile constant, not a runtime setting — adding an env var would separate it from the profile it belongs to. |
| Config field `APPIUM_MCP_COMMAND` | **Added** (plan didn't explicitly call it out but the session code needs it) | Needed a separate command field for the Appium npx path instead of reusing `chrome_mcp_command` (which would be confusing by name). |
| `NO_UI=true` for Appium | **Added beyond the plan** | The appium-mcp README recommends `NO_UI` for headless/agentic use (50–80% faster responses, 60–90% token savings). Set in `_build_appium_env()` unconditionally. |
| Readiness instructions data structure | **Slightly different** | Used a `{html}` object variant in the readiness array for the FB `<code>` element (to render `chrome://inspect/#remote-debugging` with styling) instead of JSX children. This lets each marketplace config be a self-contained data structure without JSX. |
| `MARKETPLACE_CONFIG` fallback | **Added** | Unknown marketplace IDs fall back to the FB config rather than crashing. |

## Known Limitations & Open Items

These are carried forward from the plan's "Open Questions" and identified
during implementation. None block the committed code (all is test-covered and
CI-green); they are **runtime verification items** that require a real Android
emulator to validate.

1. **Image push to emulator (HIGHEST RISK)** — Photos are passed to the agent as
   local filesystem paths. The agent needs to get them onto the emulator's
   device storage before OfferUp can select them from the gallery. The
   `appium_gesture` tool may support `push_file`, or an `adb push` equivalent
   may be needed. **Not yet validated against a real emulator.** This is the
   most likely point of failure in end-to-end testing.

2. **Emulator must be pre-started** — The system does not auto-launch the
   emulator. The user must have it running with OfferUp installed and logged in.
   This matches the Chrome pattern ("already running") and is documented in the
   readiness instructions.

3. **Appium MCP version pinning** — Currently uses `appium-mcp@latest`. Should
   be pinned to a known-good version after end-to-end validation to avoid
   breaking changes from upstream.

4. **`select_device` / `appium_session_management` argument format** — The exact
   tool argument schemas (e.g., whether `capabilities` is a flat dict or
   nested, whether `select_device` needs explicit args) are based on the
   appium-mcp README but **not validated against a running server**. May need
   adjustment after first real run.

5. **OfferUp UI changes** — The agentic approach (screenshot → reason → gesture)
   is resilient to layout changes, but OfferUp could add anti-automation
   measures. No mitigation beyond the agentic approach itself.

6. **No iOS support** — The implementation targets Android only (UiAutomator2).
   iOS would need XCUITest and a macOS host with Xcode. Not in scope.

## Architecture Notes

The key design principle that made this extension clean: **the agent loop is
backend-agnostic**. The LiteLLM tool-calling loop (`litellm.acompletion` →
`call_openai_tool`) doesn't know or care whether the MCP server is
chrome-devtools-mcp or appium-mcp. All backend-specific knowledge is isolated in
three places:

1. **`MarketplaceProfile.mcp_backend`** — selects which session opener and
   curated tool set to use
2. **`session.py`** — `open_session()` dispatches to the right MCP server
3. **`agent.py`** — `_curated_tools_for()` selects the right tool whitelist

Everything else (the fill loop, the prompt template, the API contract, the
frontend dialog) is shared. Adding a third marketplace (e.g. eBay, Mercari)
would be a new `MarketplaceProfile` entry + potentially a new curated tools set,
not a new code path.
