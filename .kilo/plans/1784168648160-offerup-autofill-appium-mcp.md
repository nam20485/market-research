---
name: OfferUp auto-fill (mobile-only)
overview: "Extend the marketplace auto-fill system with OfferUp posting support via Appium MCP + Android emulator, preserving the existing marketplace-agnostic architecture while adding a new mobile-native automation backend alongside the existing chrome-devtools-mcp browser driver."
todos:
  - id: profile-backend-abstraction
    content: Add mcp_backend field to MarketplaceProfile, make create_url optional, add OFFERUP_PROFILE to registry; update agent.py CURATED_TOOLS to be per-backend
    status: pending
  - id: appium-session-driver
    content: Add open_appium_session async context manager to session.py (or new appium_session.py) that spawns appium-mcp over stdio, creates an Android session, and yields ClientSession
    status: pending
  - id: agent-curated-tools
    content: Refactor agent.py to select curated tool lists by mcp_backend; add APPIUM_CURATED_TOOLS frozenset alongside existing CURATED_TOOLS
    status: pending
  - id: prompt-adaptation
    content: Update prompts/posting.py system prompt to support both browser and mobile-app contexts (generic agent role, conditional create_url vs app-package wording)
    status: pending
  - id: appium-config
    content: Add Appium-specific config fields to app/config.py (appium_android_home, appium_emulator_name, appium_offerup_package)
    status: pending
  - id: api-error-handling
    content: Update api/posting.py to dispatch session open based on profile.mcp_backend and provide backend-specific error messages (Chrome vs emulator)
    status: pending
  - id: frontend-offerup-button
    content: Add canPostToOfferUp logic + Post button to OfferUp ListingCard in ListingStep.jsx; reuse PostToMarketplaceDialog with OfferUp-specific readiness instructions
    status: pending
  - id: frontend-readiness-appium
    content: Add per-marketplace readiness instructions map to PostToMarketplaceDialog (emulator running, OfferUp installed+logged in, different from Chrome instructions)
    status: pending
  - id: docs-config
    content: Update .env.example, AGENTS.md with Appium prerequisites (Android SDK, JDK, emulator setup, OfferUp app pre-installed)
    status: pending
  - id: tests
    content: Add backend tests (OfferUp profile, appium session dispatch, curated tool filtering, prompt variants) and frontend tests (OfferUp button visibility, readiness instructions); run scripts/validate.ps1 -All
    status: pending
isProject: false
---

# OfferUp Auto-Fill (mobile-native, Appium MCP)

## Problem

OfferUp has **no web posting flow** — listing creation is exclusively through
their native mobile app. The existing FB Marketplace auto-fill uses
`chrome-devtools-mcp` (desktop browser automation), which cannot reach OfferUp's
create-listing form because the mobile web site redirects to app-store download
and has no sell/post UI. Reddit and OfferUp Support confirm: "listing items is
done via smartphone only."

## Options Analysis

### Option A: Chrome Mobile Emulation via chrome-devtools-mcp (CDP)

Use CDP `Emulation.setDeviceMetricsOverride` + touch emulation + mobile UA to
render OfferUp's mobile web as if on a phone.

| Pros | Cons |
|------|------|
| Reuses existing chrome-devtools-mcp infra, zero new dependencies | **OfferUp's mobile web has no posting UI** — redirects to app store |
| Same session.py pattern | chrome-devtools-mcp [issue #280](https://github.com/ChromeDevTools/chrome-devtools-mcp/issues/280): screenshots reset device mode to desktop (blocker) |
| | OfferUp detects desktop user-agent and serves desktop site regardless of emulation |
| | Would require deep spoofing (touch, UA, viewport) that still can't fabricate a form that doesn't exist |

**Verdict: NOT VIABLE.** The fundamental problem is that there is no form to fill
on the mobile web — no amount of emulation creates one.

### Option B: Appium MCP Server + Android Emulator (RECOMMENDED)

Use the official [appium/appium-mcp](https://github.com/appium/appium-mcp) MCP
server (427 stars, active Appium project) spawned over stdio — the same
protocol pattern as chrome-devtools-mcp — driving the real OfferUp Android app
on an Android emulator.

| Pros | Cons |
|------|------|
| Drives the actual OfferUp native app — full posting flow available | Heavier prerequisites: Android SDK, JDK 8+, Android emulator |
| Same MCP protocol (stdio + ClientSession) — existing agent.py fill loop reusable with different curated tools | Slower startup (~10-30s for emulator + Appium session) |
| Rich tool set: `appium_find_element`, `appium_gesture` (tap/type/scroll/swipe), `appium_screenshot`, `appium_get_page_source`, `appium_session_management` | Higher memory footprint (emulator ~2GB, Appium server embedded) |
| Official Appium project tooling, actively maintained | OfferUp may update UI, breaking element locators (mitigated by agentic snapshot-driven approach) |
| Marketplace-agnostic architecture preserved — OfferUp becomes a profile with `mcp_backend="appium"` | Linux/macOS only for emulator (Windows HAXM possible but untested) |
| `NO_UI` mode available for headless operation (50-80% faster tool responses, 60-90% token savings) | |
| AI vision element finding available (`appium_ai`) for when locators are unstable | |

**Verdict: RECOMMENDED.** This is the approach hinted at in the Phase 2 note
("Android emulator + Appium as a heavier fallback"). It preserves the
marketplace-agnostic design, reuses the LiteLLM tool-calling loop, and drives
the real app where posting actually works.

### Option C: Direct Appium WebDriver (Python Client, No MCP)

Use `Appium-Python-Client` to connect directly to a standalone Appium server,
bypassing MCP entirely.

| Pros | Cons |
|------|------|
| Direct Python integration, no MCP layer | **Breaks the MCP architecture pattern** — no `load_mcp_tools`/`call_openai_tool` |
| | Requires separate Appium server process lifecycle |
| | Would need a parallel fill loop implementation (can't reuse agent.py) |
| | Adds ~200+ lines of Python driver code vs ~60 for Appium MCP session |

**Verdict: NOT RECOMMENDED.** Architectural divergence; doubles the maintenance
surface with a parallel automation system that can't share the agent loop.

### Option D: Reverse-Engineered OfferUp Internal API

Use the unofficial `planetzero/offerup` Python client or scrape the internal API
endpoints the OfferUp mobile app uses.

| Pros | Cons |
|------|------|
| Fastest execution (no UI automation) | **Extremely fragile** — any OfferUp app update can break the API |
| No emulator/browser needed | Authentication complexity (OAuth + device fingerprinting) |
| | Likely violates OfferUp Terms of Service |
| | No official API exists; relying on reverse engineering is legally risky |
| | Image upload endpoints especially unstable |

**Verdict: NOT RECOMMENDED.** Too fragile, legally questionable, and
unsustainable for any ongoing use.

## Recommendation

**Option B: Appium MCP + Android Emulator.** Rationale:

1. **Works** — OfferUp's real app has a full posting flow that can be automated.
2. **Architecturally consistent** — same MCP stdio protocol, same agent fill
   loop, same single-request session lifecycle. OfferUp becomes a profile, not
   a rewrite.
3. **Agentic resilience** — the snapshot-driven approach (screenshot → reason →
   gesture) handles OfferUp UI changes better than fixed locators.
4. **Community-backed** — appium-mcp is official Appium project tooling with
   active maintenance and vision support.
5. **Fill-only scope preserved** — the agent stops before "Post" just like FB.

## Architecture Changes

### 1. Profile Backend Abstraction (`profiles.py`)

Add `mcp_backend` field to `MarketplaceProfile`:

```python
@dataclass(frozen=True)
class MarketplaceProfile:
    id: str
    label: str
    create_url: str                    # "" for app-based marketplaces
    fill_instructions: str
    mcp_backend: str = "chrome-devtools"  # "chrome-devtools" or "appium"
    app_package: str = ""                 # Android package (OfferUp: "com.offerup")
    field_hints: dict[str, str] = field(default_factory=dict)
```

Add `OFFERUP_PROFILE`:
- `id="offerup"`, `label="OfferUp"`, `create_url=""`, `mcp_backend="appium"`,
  `app_package="com.offerup"`
- `fill_instructions`: "Launch the OfferUp app if not already open.
  Tap the '+' or 'Sell' button to start a new listing. Add all provided photos
  from the local paths. Fill the title field, description field, and price field
  (if provided). Select the most appropriate category if obvious from the item
  type. Leave condition as the default. Do NOT tap 'Post', 'Publish', 'Sell',
  or any submission button — stop once fields are filled so the user can review
  and submit manually."

Update `FACEBOOK_MARKETPLACE_PROFILE` to add `mcp_backend="chrome-devtools"`
explicitly (was the implicit default).

### 2. Session Dispatch (`session.py`)

Split into two session openers or add a dispatch wrapper:

```python
@asynccontextmanager
async def open_session(
    profile: MarketplaceProfile,
    settings: Settings | None = None,
) -> AsyncIterator[ClientSession]:
    if profile.mcp_backend == "appium":
        async with open_appium_session(profile, settings) as s:
            yield s
    else:
        async with open_browser_session(settings) as s:
            yield s
```

New `open_appium_session`:
- Build `StdioServerParameters` for `npx appium-mcp@latest`
- Set env: `ANDROID_HOME`, `NO_UI=true` (headless), `CAPABILITIES_CONFIG` (if set)
- `async with stdio_client(params) → ClientSession → initialize()`
- Call `appium_session_management(action="create", platform="android")` to
  create an emulator session targeting the OfferUp app
- Yield the `ClientSession`; everything tears down on context exit

### 3. Agent Curated Tools (`agent.py`)

Split curated tools by backend:

```python
CHROME_CURATED_TOOLS = frozenset({...})  # existing set, renamed

APPIUM_CURATED_TOOLS = frozenset({
    "appium_session_management",
    "appium_find_element",
    "appium_gesture",         # tap, type, scroll, swipe, long_press
    "appium_screenshot",
    "appium_get_page_source",
    "appium_app_lifecycle",   # launch OfferUp app
    "appium_context",          # switch NATIVE_APP / WEBVIEW if needed
    "appium_mobile_device_control",  # lock/unlock if needed
    "appium_driver_settings",
})
```

The `fill()` function selects the tool frozenset based on `profile.mcp_backend`:
```python
curated = APPIUM_CURATED_TOOLS if profile.mcp_backend == "appium" else CHROME_CURATED_TOOLS
tools = [t for t in all_tools if t["function"]["name"] in curated]
```

### 4. Prompt Adaptation (`prompts/posting.py`)

The existing template says "browser-automation agent" and "Create-listing URL:".
Make these conditional on backend:

- For `chrome-devtools`: keep existing "browser-automation agent" + URL wording
- For `appium`: use "mobile-app automation agent" + "App package: com.offerup"

Implementation: pass `mcp_backend` and `app_package` to
`build_posting_system_prompt` and branch the relevant template lines. Or use a
single template with conditional phrasing driven by the profile.

### 5. Config (`app/config.py`)

Add alongside existing chrome-mcp settings:

```python
appium_android_home: str = ""       # ANDROID_HOME env; blank → inherit from environment
appium_emulator_name: str = ""      # blank → auto-select first available emulator
appium_offerup_package: str = "com.offerup"  # Android package name
appium_mcp_extra_args: str = ""     # extra args for npx appium-mcp
```

### 6. API Error Handling (`api/posting.py`)

Replace hardcoded `open_browser_session(settings)` with
`open_session(profile, settings)` dispatch. Update the 502 error message to be
backend-specific:

- Chrome: existing message about Chrome + remote debugging
- Appium: "Make sure an Android emulator is running with OfferUp installed and
  logged in, and try again."

### 7. Frontend: OfferUp Post Button (`ListingStep.jsx`)

Add `canPostToOfferUp` logic (mirrors `canPostToFacebook`):
```js
const canPostToOfferup =
  capabilities?.enabled &&
  capabilities?.marketplaces?.some(m => m.id === 'offerup') &&
  listing?.offerup
```

Add Post button to the OfferUp ListingCard's `headerExtra`.

Render `<PostToMarketplaceDialog marketplace="offerup" ... />` on click.
Need a separate `showOfferupDialog` state (or generalize to handle both).

### 8. Frontend: Per-Marketplace Readiness Instructions (`PostToMarketplaceDialog.jsx`)

The readiness screen currently shows Chrome-specific instructions. Make these
per-marketplace via a readiness-instructions map:

```js
const READINESS = {
  facebook_marketplace: [
    'Open Chrome and log into Facebook',
    'Enable remote debugging once at chrome://inspect/#remote-debugging',
    'Keep Chrome open',
  ],
  offerup: [
    'Start an Android emulator (e.g. via Android Studio > Device Manager)',
    'Install OfferUp from Play Store and log in',
    'Ensure ADB is on your PATH and ANDROID_HOME is set',
  ],
}
```

The dialog selects instructions based on the `marketplace` prop. The dialog
component itself is already marketplace-agnostic — it reads the `marketplace`
prop and passes it to the API.

### 9. `.env.example` Updates

Add under existing posting block:

```
# OfferUp (Appium MCP + Android emulator; local-only)
APPIUM_ANDROID_HOME=          # blank → inherit ANDROID_HOME from environment
APPIUM_EMULATOR_NAME=         # blank → auto-select first available emulator
APPIUM_OFFERUP_PACKAGE=com.offerup
APPIUM_MCP_EXTRA_ARGS=
```

## Task List

| # | Task | Files |
|---|------|-------|
| 1 | Add `mcp_backend`, `app_package` fields to `MarketplaceProfile`; add `OFFERUP_PROFILE` to registry; update FB profile with explicit `mcp_backend` | `app/services/posting/profiles.py` |
| 2 | Add `APPIUM_CURATED_TOOLS`; refactor `fill()` to select curated set by `profile.mcp_backend` | `app/services/posting/agent.py` |
| 3 | Add `open_appium_session` context manager + `open_session` dispatch wrapper | `app/services/posting/session.py` |
| 4 | Adapt system prompt template for Appium backend (mobile-app agent role, app package instead of URL) | `app/prompts/posting.py` |
| 5 | Add Appium config fields to `Settings` | `app/config.py` |
| 6 | Update `/api/post/fill` to use `open_session(profile, settings)` dispatch and backend-specific error messages | `app/api/posting.py` |
| 7 | Add OfferUp post button visibility + dialog rendering in `ListingStep.jsx` | `frontend/src/components/ListingStep.jsx` |
| 8 | Add per-marketplace readiness instructions map to `PostToMarketplaceDialog.jsx` | `frontend/src/components/PostToMarketplaceDialog.jsx` |
| 9 | Update `.env.example`, `AGENTS.md` with Appium prerequisites | `.env.example`, `AGENTS.md` |
| 10 | Backend tests: OfferUp profile in registry, Appium session dispatch, curated tool selection by backend, prompt variants | `tests/test_posting.py`, `tests/test_posting_agent.py`, `tests/test_posting_session.py` |
| 11 | Frontend tests: OfferUp button visibility, readiness instructions per-marketplace | `ListingStep.test.jsx`, `PostToMarketplaceDialog.test.jsx` |
| 12 | Run `pwsh -NoProfile -File ./scripts/validate.ps1 -All` | — |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Android emulator startup is slow (~10-30s) | Session scoped to single request; frontend shows progress. Document expected timing. |
| OfferUp app UI changes break element locators | Agentic snapshot-driven approach (screenshot → reason → gesture) adapts to layout changes. No hardcoded selectors. |
| OfferUp detects automation and blocks | Appium uses UiAutomator2 which drives real native UI; harder to detect than web automation. Risk is low for personal use. |
| Heavy prerequisites (Android SDK, JDK, emulator) | Gated by `POSTING_ENABLED` + profile presence in capabilities. Frontend shows clear setup instructions. AGENTS.md documents prerequisites. |
| Appium MCP is newer than chrome-devtools-mcp | Official Appium project, 427 stars, 574 commits, active maintenance. Apache 2.0 license. |
| Two MCP backends increase maintenance | Same protocol (stdio + ClientSession), same fill loop, same config pattern. Divergence limited to curated tools list and session opening. |

## Open Questions

1. **Image push to emulator**: Appium's `appium_gesture` with `push_file` or
   the emulator's shared folder mechanism needs to be used to get photos into
   the device gallery before OfferUp can select them. The agent will need
   instructions on the preferred mechanism (likely `adb push` via
   `appium_gesture(action="push_file")` or pre-staging in shared storage).
   This should be prototyped early — it's the riskiest unknown.

2. **Emulator auto-launch**: Should the system launch the emulator
   automatically if none is running, or require the user to have it pre-started?
   Recommendation: require pre-started (simpler, matches Chrome pattern of
   "already running").

3. **Appium MCP version pinning**: `npx appium-mcp@latest` may pull breaking
   changes. Consider pinning to a known-good version once validated.
