# Agent Architecture Handoff: Market Research & Pricing Strategy

**To:** Agent Development Team
**From:** Nathan
**Subject:** Feedback Requested: Multi-Tool Research Workflow & Pricing Logic for Qwen 3.7-plus

## Context
As we finalize the research and generation pipeline for our automated listing app (FastAPI + LiteLLM + Uvicorn), we are updating the agent's tool-calling strategy. We are using **Qwen 3.7-plus** as the core reasoning/vision model and **Tavily** for web research. 

After reviewing the limitations of relying solely on Tavily for real-time local market pricing (due to FB Marketplace/OfferUp being walled gardens), we are proposing a **Multi-Tool Agentic Workflow**. 

Please review the recommendations below and provide feedback on implementation support, API integration, and prompt engineering.

---

> ## Reviewer's Note on Current Architecture (read first)
>
> Before the item-by-item replies, one framing correction that affects several
> recommendations: **the app is not an agentic tool-calling loop today.** It is a
> linear, Python-orchestrated three-stage pipeline, and the model never receives a
> `tools=` schema. Each stage makes a single completion call that must return a fixed
> JSON object, which we parse (`app/services/json_utils.py`):
>
> 1. **Identify** (`POST /api/identify` → `IdentificationService`) — a *vision* call
>    (`LLMService.vision`) extracts brand/model/attributes from the photo(s) + text,
>    then optionally does one Tavily lookup to enrich the top candidate. Locks when
>    confidence ≥ 0.8 (`LOCK_CONFIDENCE_THRESHOLD`).
> 2. **Research** (`POST /api/research` → `ResearchService`) — Python builds two fixed
>    Tavily queries (`"<item> sold price used"`, `"<item> for sale used marketplace"`),
>    then a *chat* call synthesizes a `price_range/demand/marketing_angle` report from
>    the snippets.
> 3. **Listing** (`POST /api/listing` → `ListingService`) — a chat call generates
>    copy-paste FB Marketplace + OfferUp title/description. Gated on
>    `research_approved`.
>
> Implications used throughout the replies below:
> - "Add a tool to the LiteLLM tool schema" (§1) isn't the shape we have. Adding a
>   second data source is a new `SearchProvider`-style client + an extra
>   orchestrated step in `ResearchService`, **not** a model-driven function call.
>   That's actually *good news* — deterministic control flow, no context-limit risk.
> - The **model is configured via `.env`, not hard-coded to Qwen 3.7-plus.** Defaults
>   are `gpt-4o-mini` for both chat and vision (`app/config.py`). Chat and vision have
>   independent `*_api_base`/`*_api_key` so a text-only provider (e.g. Z.AI `zai/`)
>   can be paired with a separate vision provider — see the repo's AGENTS.md.
> - **No caching, no Redis, no Playwright/CDP, no eBay/SerpApi, and no posting stage
>   exist in the codebase yet.** Sections 4 and 5 are greenfield, not integrations.
>
> — Dev team

---

## 1. Multi-Tool Agentic Workflow (Identification vs. Pricing)

**The Problem:** Tavily is excellent for identifying items and finding original MSRP from the public web, but it cannot reliably scrape active, walled-garden local listings on FB Marketplace or OfferUp for real-time Fair Market Value (FMV).

**The Recommendation:** Implement a two-step tool-calling loop in LiteLLM.
1. **Tool 1: Tavily Search.** Used *only* for item identification (Brand, Model, Original MSRP, Specs).
2. **Tool 2: eBay Sold/Completed Listings API (via SerpApi or direct API).** Used to find the actual recent FMV based on the exact identified model. eBay *sold* data is the most reliable public proxy for local resale value.

**Feedback Required:**
- [ ] Can we easily add a secondary tool (eBay/SerpApi) to the LiteLLM tool schema without hitting token/context limits?
- [ ] Do we have an existing SerpApi key, or should DevOps provision one?
- [ ] How should the agent handle cases where the item is too niche and returns zero eBay sold results? (Fallback to Tavily for general "asking price" research?)

> **Dev feedback — §1**
>
> **On the two-step design:** Strongly agree with the *substance* — Tavily for
> identity/MSRP, a sold-comps source for FMV. But not as a "LiteLLM tool schema." We
> already abstract search behind `SearchProvider` (ABC in `app/services/search.py`,
> Tavily is the one impl). The clean move is a parallel `CompsProvider` (eBay/SerpApi)
> client and a second orchestrated step inside `ResearchService._gather_results`, then
> pass both result sets into `build_research_prompt`. This is a ~1–2 day change and
> touches: `search.py` (or a new `comps.py`), `research.py`, `prompts/research.py`,
> `schemas/research.py`, `config.py`, and tests.
>
> - **Token/context limits — not a concern.** Because we don't hand the model a tool
>   catalog, there's no schema bloat. We already cap comp volume
>   (`MAX_RESULTS_PER_QUERY = 5`) and query length (`MAX_SEARCH_QUERY_LEN = 400`,
>   Tavily's hard limit). We'd apply the same trimming to eBay snippets before they
>   hit the synthesis prompt.
> - **SerpApi key — we do NOT have one.** Config only knows `tavily_api_key`
>   (`app/config.py`). DevOps needs to provision it and, per AGENTS.md, add it to
>   **GCP Secret Manager** for Cloud Run (`gcloud secrets versions add`) plus `.env`
>   for local — never committed. We'd add a `serpapi_api_key` / `ebay_*` field to
>   `Settings`. **Recommendation:** prefer the direct eBay Browse/Marketplace Insights
>   API over SerpApi if we can get production access — cheaper per call and cacheable
>   (§4); SerpApi is the faster-to-integrate fallback. Note eBay's true *sold/completed*
>   data requires the **Marketplace Insights API** (restricted access approval), so
>   SerpApi's `ebay` engine may be the pragmatic v1.
> - **Zero-results fallback — yes, and cheap to do here.** Since we control the flow,
>   the fallback is just Python: if the comps step returns 0 rows, skip it and let the
>   existing Tavily "asking price" queries carry the report, and set a flag in the
>   prompt so the model labels the range as *asking-price-derived, lower confidence*.
>   Also surface a `price_confidence` field in `PriceRange` so the UI can show it. No
>   agent reasoning needed.

---

## 2. Vision-to-Text Preprocessing Pipeline

**The Problem:** Passing raw images directly to search APIs or relying on the LLM to simultaneously process an image and format a complex search query can lead to hallucinated or overly broad search terms.

**The Recommendation:** Leverage Qwen 3.7-plus's multimodal capabilities in a dedicated preprocessing step.
1. Pass the user's image to Qwen 3.7-plus with a system prompt: *"Analyze this image. Identify the exact brand, model, color, condition, and any distinguishing features. Output a highly detailed, text-only description."*
2. Pass this generated text description to Tavily for the identification search.

**Feedback Required:**
- [ ] Should this be a dedicated "Vision Agent" node in our workflow, or handled via a system prompt in the main research loop?
- [ ] Are there latency concerns with making two sequential LLM calls (Vision -> Text -> Tool Call) for the user?

> **Dev feedback — §2**
>
> **This is already built — it's the `identify` stage.** `IdentificationService.identify`
> (`app/services/identification.py`) does exactly the recommended vision→text step: it
> calls `LLMService.vision` with `build_identify_prompt`, which instructs the model to
> return brand/model/color/attributes as structured JSON (`app/prompts/identify.py`).
> The research stage then consumes that locked, text-only item label
> (`ResearchService._item_label`) — raw images never reach Tavily. So the
> hallucination risk you're guarding against is already mitigated by design.
>
> - **Dedicated node vs. system prompt — it's already a dedicated node** (separate
>   endpoint + service), which we prefer over folding vision into the research loop.
>   Keeping it separate is what lets the UI run the stateless *refinement* conversation
>   (candidates + `follow_up_question` + confidence-gated `locked`) before we spend a
>   Tavily/eBay call. Recommend keeping this boundary.
> - **One refinement we should make:** the identify prompt asks for brand/model/attrs
>   but not an explicit *condition* assessment. §3 wants a visual condition multiplier,
>   so we should extend `build_identify_prompt` + `CandidateItem` to capture a
>   structured `condition`/`condition_notes` at identify time and thread it through
>   `ResearchRequest.condition` (currently free-form/optional).
> - **Latency:** the two calls are **not** on the same request — they're separate user
>   steps (identify, then approve, then research), so no compounded blocking wait. The
>   real cost is that vision + a possible enrichment search already make identify the
>   slowest call; we've mitigated perceived latency with the `StatusLog` progressive
>   updates (per AGENTS.md). If we later chain vision→research in one shot, budget for
>   the vision call being the dominant term and keep the `StatusLog` steps.

---

## 3. Dynamic Pricing & Haggle Logic

**The Problem:** Sellers often price items based on emotion, while buyers expect to haggle. The agent needs to output a strategic pricing structure, not just a single number.

**The Recommendation:** Update the final synthesis system prompt for Qwen 3.7-plus. Once the FMV is established via the eBay tool, instruct the model to output a structured pricing strategy:
* **Listing Price:** FMV + 15% (to absorb buyer haggling).
* **Firm Bottom Price:** FMV - 10% (the absolute minimum acceptable).
* **Condition Adjustment:** Apply a +/- multiplier based on the visual condition assessed in Step 2.

**Feedback Required:**
- [ ] Can we enforce a strict JSON output schema from Qwen for the final pricing data so it can be directly injected into the Playwright/CDP form-filling payload?
- [ ] Should we allow the user to override the "Haggle Percentage" via the app's UI?

> **Dev feedback — §3**
>
> **This logic does not exist yet and is the highest-value net-new work.** Today
> `ResearchResponse` only carries a `PriceRange` (low/high/currency/summary) plus
> `demand`/`marketing_angle` (`app/schemas/research.py`), and the listing stage just
> takes whatever single `price` the client sends (`ListingRequest.price`). There is no
> listing/firm-bottom/haggle structure anywhere.
>
> - **Do the arithmetic in Python, not the prompt.** FMV+15% / FMV−10% are
>   deterministic — asking the LLM to compute them invites arithmetic drift and makes
>   outputs non-reproducible. Recommend: the model returns the *evidence-based FMV*
>   (which it must, since it's grounded in comps), and `ResearchService` computes
>   `listing_price`, `firm_bottom`, and applies the condition multiplier in code. New
>   `PricingStrategy` schema with explicit fields; the LLM stays responsible only for
>   FMV + a rationale string.
> - **Strict JSON — yes, but the current mechanism is fragile.** We currently coerce
>   JSON via a prompt instruction + a tolerant parser (`parse_json_object` strips
>   markdown fences etc.). That's fine for prose fields but risky for numbers headed
>   into an automated form-fill. Two hardening options: (a) since numeric derivation
>   moves to Python, only the FMV number comes from the model and Pydantic validates
>   it; (b) if the provider supports it, enable LiteLLM `response_format=json_object`.
>   Caveat from AGENTS.md: some providers (Z.AI `zai/`) are OpenAI-compatible but may
>   not honor structured-output flags — keep the tolerant parser as a fallback and
>   validate with Pydantic regardless.
> - **Condition multiplier:** depends on capturing structured condition at identify
>   time (see §2). Define the multiplier table in code/config, not the prompt.
> - **User-overridable haggle %:** yes — cheap and worth it. Add optional
>   `haggle_pct` / `floor_pct` to `ResearchRequest` (defaulting to 15/10), persist the
>   user's preference client-side following the existing `localStorage` hook pattern
>   (`useTheme.js` / `useRecentQueries.js`, per AGENTS.md). Because the math is in
>   Python, the override is a trivial parameter, not a prompt change.
> - **Re: "inject into the Playwright/CDP payload"** — note there is no form-filling
>   payload consumer yet (see §5). Design the `PricingStrategy` schema now so it's
>   serialization-ready, but the injection target is future work.

---

## 4. Caching Strategy for Research APIs

**The Problem:** Repeatedly researching common items (e.g., "iPhone 13 Pro 128GB", "Dyson V11") will burn through Tavily and SerpApi credits rapidly.

**The Recommendation:** Implement a caching layer (Redis or DiskCache) in the FastAPI backend. 
* Cache key: Normalized string of the identified Brand + Model.
* Cache TTL: 7 days for eBay sold data (prices fluctuate), 30 days for MSRP/Specs.

**Feedback Required:**
- [ ] Do we already have a Redis instance running in our Proxmox/Dev environment that the FastAPI app can connect to?
- [ ] Should we implement a simple local SQLite/DiskCache fallback if Redis is unavailable?

> **Dev feedback — §4**
>
> **No caching exists today** (no Redis/DiskCache dep in `pyproject.toml`, no cache
> code). Agree it's worth adding once we're paying per call for eBay/SerpApi — right
> now Tavily is the only metered call and volume is low, so this is a "before §1 ships
> to prod" item, not urgent for local dev.
>
> - **Redis availability — decision needed from you/DevOps.** Prod backend is **GCP
>   Cloud Run**, not the Proxmox box (per AGENTS.md). Cloud Run scales to zero
>   (`min_instance_count = 0`) and has no attached Redis, so a Redis-only design means
>   provisioning **Memorystore / Upstash / Cloud Run + external Redis** and managing a
>   connection string secret. That's real infra cost for a free-tier-oriented deploy.
> - **Recommendation: make the cache an interface, default to DiskCache/SQLite, treat
>   Redis as opt-in.** Mirror the `SearchProvider` ABC pattern: a `CacheBackend`
>   protocol with `DiskCacheBackend` (default) and `RedisCacheBackend` (used only when
>   a `redis_url` is set in `Settings`). This keeps local + Cloud Run working with zero
>   extra infra and lets the Proxmox/prod path flip to Redis via env. Note: on Cloud
>   Run's ephemeral, scale-to-zero filesystem a DiskCache won't persist across
>   instances — so for prod the realistic choices are a shared Redis *or* a small
>   Firestore/GCS-backed store. DiskCache is genuinely useful for local/dev and the
>   Proxmox box; don't assume it buys us much on Cloud Run.
> - **Cache-key + TTL design is sound.** Normalized `brand + model` key, 7d for FMV /
>   30d for MSRP/specs. Add: normalize case/whitespace and include a schema version in
>   the key so a prompt/schema change invalidates stale entries. Cache at the
>   *provider-response* layer (Tavily/eBay results), not the synthesized report, so a
>   prompt tweak doesn't require a cache flush.

---

## 5. Browser Automation Execution (MCP vs. Playwright CDP)

**Context:** For the actual posting phase to FB Marketplace and OfferUp, we are utilizing the Chrome DevTools Protocol (CDP) attached to an existing Chrome session to bypass anti-bot detection.

**The Recommendation:** 
* Use **Deterministic Playwright CDP** scripts for standard form filling (fast, reliable).
* Expose the **Chrome DevTools MCP Server** to the LLM *only* as a fallback mechanism. If a Playwright selector fails (e.g., OfferUp changes their DOM), the agent can use the MCP tools to visually/semantically locate the new UI elements and adapt.

**Feedback Required:**
- [ ] Is the team comfortable maintaining the deterministic Playwright selectors for FB/OfferUp?
- [ ] Do we need to wrap the MCP server in a specific Python SDK to pass its tools to LiteLLM dynamically?
