import { logger } from './logger.js'

// API client for the market-research backend.
// Calls target `${API_BASE}/api/...` paths.
//
// Local / Docker Compose: leave VITE_BACKEND_URL unset so API_BASE is '' and
// paths stay relative. Vite (or nginx) then proxies /api and /healthz to the
// backend — see BACKEND_PROXY_TARGET in vite.config.js / docker-compose.yml.
//
// Cloudflare Pages: set VITE_BACKEND_URL at build time to the public Cloud Run
// origin so the static bundle calls the backend cross-origin.
const API_BASE = import.meta.env.VITE_BACKEND_URL ?? ''

/**
 * Format FastAPI / generic error bodies for display.
 * FastAPI 422 responses use `detail` as an array of objects.
 * @param {unknown} detail
 * @returns {string}
 */
function formatErrorDetail(detail) {
  if (detail === null || detail === undefined) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((entry) => {
        if (typeof entry === 'string') return entry
        if (entry && typeof entry === 'object') {
          const loc = Array.isArray(entry.loc)
            ? entry.loc.filter((part) => part !== 'body').join('.')
            : ''
          const msg = entry.msg ?? JSON.stringify(entry)
          return loc ? `${loc}: ${msg}` : msg
        }
        return String(entry)
      })
      .join('; ')
  }
  if (typeof detail === 'object') {
    return JSON.stringify(detail)
  }
  return String(detail)
}

async function parseJsonOrThrow(response) {
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = formatErrorDetail(body.detail ?? body.message ?? body)
    } catch {
      // response had no JSON body; fall back to statusText
    }
    const message = `Request failed (${response.status}): ${detail}`
    logger.error(message)
    throw new Error(message)
  }
  return response.json()
}

/**
 * Map a locked CandidateItem from identify into the research/listing request shape.
 * Identify uses `name`; research/listing schemas use `item_name`.
 * @param {Record<string, unknown>} item
 * @returns {{
 *   item_name: string,
 *   brand: string | null,
 *   model: string | null,
 *   attributes: Record<string, string>,
 *   condition: string | null,
 * }}
 */
function itemToRequestFields(item) {
  const name = item?.item_name ?? item?.name ?? item?.title ?? item?.label
  if (!name || typeof name !== 'string') {
    throw new Error('Locked item is missing a name.')
  }
  return {
    item_name: name,
    brand: typeof item.brand === 'string' ? item.brand : null,
    model: typeof item.model === 'string' ? item.model : null,
    attributes:
      item.attributes && typeof item.attributes === 'object' && !Array.isArray(item.attributes)
        ? item.attributes
        : {},
    condition: typeof item.condition === 'string' ? item.condition : null,
  }
}

/**
 * Build a short research summary string for listing generation.
 *
 * Prefers the computed `pricing.listing_price` (Phase 3 dynamic pricing)
 * over the raw `price_range` when both are present, since it reflects the
 * haggle-adjusted price the seller should actually list at.
 *
 * @param {Record<string, unknown> | null | undefined} research
 * @returns {string | null}
 */
function researchSummary(research) {
  if (!research || typeof research !== 'object') return null
  const parts = []
  const pricing = research.pricing
  if (
    pricing &&
    typeof pricing === 'object' &&
    typeof pricing.listing_price === 'number'
  ) {
    const currency = typeof pricing.currency === 'string' ? pricing.currency : 'USD'
    parts.push(`Price: ${currency} ${pricing.listing_price}`)
  } else if (research.price_range) {
    const range = research.price_range
    if (typeof range === 'string') {
      parts.push(`Price: ${range}`)
    } else if (typeof range === 'object') {
      const summary = range.summary
      if (summary) {
        parts.push(`Price: ${summary}`)
      } else if (range.low != null || range.high != null) {
        parts.push(`Price: ${range.low ?? '?'}–${range.high ?? '?'}`)
      }
    }
  }
  if (typeof research.demand === 'string' && research.demand) {
    parts.push(`Demand: ${research.demand}`)
  }
  if (typeof research.marketing_angle === 'string' && research.marketing_angle) {
    parts.push(`Angle: ${research.marketing_angle}`)
  }
  return parts.length ? parts.join('. ') : null
}

/**
 * Check backend health.
 * @returns {Promise<unknown>}
 */
export async function checkHealth() {
  logger.info('GET', `${API_BASE}/healthz`)
  const response = await fetch(`${API_BASE}/healthz`)
  return parseJsonOrThrow(response)
}

/**
 * Submit (or refine) an item identification request.
 *
 * The backend is stateless, so every call resends the full accumulated
 * conversation/attributes context along with the latest description and
 * any newly attached photos.
 *
 * @param {{
 *   description: string,
 *   images?: File[],
 *   context?: unknown,
 * }} params
 * @returns {Promise<{ candidates: unknown[], locked: boolean, context?: unknown }>}
 */
export async function identifyItem({ description, images = [], context }) {
  const formData = new FormData()
  formData.append('description', description ?? '')
  if (context !== undefined && context !== null) {
    // Backend accepts known_attributes + conversation as JSON form fields.
    if (typeof context === 'object' && !Array.isArray(context)) {
      formData.append(
        'known_attributes',
        JSON.stringify(context.known_attributes ?? {}),
      )
      formData.append(
        'conversation',
        JSON.stringify(context.conversation ?? []),
      )
    } else if (typeof context === 'string') {
      formData.append('known_attributes', context)
    }
  }
  for (const image of images) {
    formData.append('images', image)
  }

  logger.info('POST', `${API_BASE}/api/identify`, {
    descriptionLen: (description ?? '').length,
    imageCount: images.length,
  })
  const response = await fetch(`${API_BASE}/api/identify`, {
    method: 'POST',
    body: formData,
  })
  return parseJsonOrThrow(response)
}

/**
 * Request a market research report for a locked item.
 *
 * @param {{
 *   item: Record<string, unknown>,
 *   haggle_pct?: number | null,
 *   floor_pct?: number | null,
 * }} params
 * @returns {Promise<{
 *   price_range: unknown,
 *   demand: unknown,
 *   marketing_angle: string,
 *   sources: { title: string, url: string }[],
 *   pricing: {
 *     fmv: number,
 *     listing_price: number,
 *     firm_bottom: number,
 *     currency: string,
 *     haggle_pct: number,
 *     floor_pct: number,
 *     condition_multiplier: number,
 *     confidence: 'sold_comps' | 'asking_price' | 'unknown',
 *     rationale: string | null,
 *   } | null | undefined,
 * }>}
 */
export async function requestResearch({ item, haggle_pct, floor_pct }) {
  const body = itemToRequestFields(item)
  if (haggle_pct !== undefined && haggle_pct !== null) {
    body.haggle_pct = haggle_pct
  }
  if (floor_pct !== undefined && floor_pct !== null) {
    body.floor_pct = floor_pct
  }
  logger.info('POST', `${API_BASE}/api/research`, {
    item_name: body.item_name,
    brand: body.brand,
  })
  const response = await fetch(`${API_BASE}/api/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return parseJsonOrThrow(response)
}

/**
 * Request generated marketplace listing content for the approved item.
 *
 * @param {{ item: Record<string, unknown>, research: Record<string, unknown> }} params
 * @returns {Promise<{
 *   facebook_marketplace: { title: string, description: string },
 *   offerup: { title: string, description: string },
 * }>}
 */
export async function generateListing({ item, research }) {
  const body = {
    ...itemToRequestFields(item),
    research_approved: true,
    research_summary: researchSummary(research),
  }
  logger.info('POST', `${API_BASE}/api/listing`, {
    item_name: body.item_name,
    brand: body.brand,
  })
  const response = await fetch(`${API_BASE}/api/listing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return parseJsonOrThrow(response)
}

/**
 * Check whether the backend can auto-fill marketplace listings (local-only
 * feature; disabled e.g. when pointed at Cloud Run).
 * @returns {Promise<{ enabled: boolean, marketplaces: { id: string, label: string }[] }>}
 */
export async function getPostingCapabilities() {
  logger.info('GET', `${API_BASE}/api/post/capabilities`)
  const response = await fetch(`${API_BASE}/api/post/capabilities`)
  return parseJsonOrThrow(response)
}

/**
 * Auto-fill a marketplace's create-listing form via the backend's local
 * browser-automation agent. Connect + fill + teardown happen server-side in
 * a single request; the agent stops before Publish/Post for the user to submit.
 *
 * @param {{
 *   marketplace: string,
 *   listing: { title?: string, description?: string },
 *   price?: number | string | null,
 *   images?: File[],
 * }} params
 * @returns {Promise<{ status: string, steps_summary: string[], screenshot?: string | null }>}
 */
export async function fillMarketplaceListing({ marketplace, listing, price, images = [] }) {
  const formData = new FormData()
  formData.append('marketplace', marketplace)
  formData.append('title', listing?.title ?? '')
  formData.append('description', listing?.description ?? '')
  if (price !== undefined && price !== null && price !== '') {
    formData.append('price', String(price))
  }
  for (const image of images) {
    formData.append('images', image)
  }

  logger.info('POST', `${API_BASE}/api/post/fill`, { marketplace, imageCount: images.length })
  const response = await fetch(`${API_BASE}/api/post/fill`, {
    method: 'POST',
    body: formData,
  })
  return parseJsonOrThrow(response)
}
