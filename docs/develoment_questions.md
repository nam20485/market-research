# Agent Architecture Handoff: Market Research & Pricing Strategy

**To:** Agent Development Team
**From:** Nathan
**Subject:** Feedback Requested: Multi-Tool Research Workflow & Pricing Logic for Qwen 3.7-plus

## Context
As we finalize the research and generation pipeline for our automated listing app (FastAPI + LiteLLM + Uvicorn), we are updating the agent's tool-calling strategy. We are using **Qwen 3.7-plus** as the core reasoning/vision model and **Tavily** for web research. 

After reviewing the limitations of relying solely on Tavily for real-time local market pricing (due to FB Marketplace/OfferUp being walled gardens), we are proposing a **Multi-Tool Agentic Workflow**. 

Please review the recommendations below and provide feedback on implementation support, API integration, and prompt engineering.

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

---

## 2. Vision-to-Text Preprocessing Pipeline

**The Problem:** Passing raw images directly to search APIs or relying on the LLM to simultaneously process an image and format a complex search query can lead to hallucinated or overly broad search terms.

**The Recommendation:** Leverage Qwen 3.7-plus's multimodal capabilities in a dedicated preprocessing step.
1. Pass the user's image to Qwen 3.7-plus with a system prompt: *"Analyze this image. Identify the exact brand, model, color, condition, and any distinguishing features. Output a highly detailed, text-only description."*
2. Pass this generated text description to Tavily for the identification search.

**Feedback Required:**
- [ ] Should this be a dedicated "Vision Agent" node in our workflow, or handled via a system prompt in the main research loop?
- [ ] Are there latency concerns with making two sequential LLM calls (Vision -> Text -> Tool Call) for the user?

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

---

## 4. Caching Strategy for Research APIs

**The Problem:** Repeatedly researching common items (e.g., "iPhone 13 Pro 128GB", "Dyson V11") will burn through Tavily and SerpApi credits rapidly.

**The Recommendation:** Implement a caching layer (Redis or DiskCache) in the FastAPI backend. 
* Cache key: Normalized string of the identified Brand + Model.
* Cache TTL: 7 days for eBay sold data (prices fluctuate), 30 days for MSRP/Specs.

**Feedback Required:**
- [ ] Do we already have a Redis instance running in our Proxmox/Dev environment that the FastAPI app can connect to?
- [ ] Should we implement a simple local SQLite/DiskCache fallback if Redis is unavailable?

---

## 5. Browser Automation Execution (MCP vs. Playwright CDP)

**Context:** For the actual posting phase to FB Marketplace and OfferUp, we are utilizing the Chrome DevTools Protocol (CDP) attached to an existing Chrome session to bypass anti-bot detection.

**The Recommendation:** 
* Use **Deterministic Playwright CDP** scripts for standard form filling (fast, reliable).
* Expose the **Chrome DevTools MCP Server** to the LLM *only* as a fallback mechanism. If a Playwright selector fails (e.g., OfferUp changes their DOM), the agent can use the MCP tools to visually/semantically locate the new UI elements and adapt.

**Feedback Required:**
- [ ] Is the team comfortable maintaining the deterministic Playwright selectors for FB/OfferUp?
- [ ] Do we need to wrap the MCP server in a specific Python SDK to pass its tools to LiteLLM dynamically?
