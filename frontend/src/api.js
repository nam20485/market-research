// API client for the market-research backend.
// All calls target relative `/api/...` paths, proxied to the FastAPI
// backend (default `http://localhost:8000`) by Vite's dev server (see
// vite.config.js) and by the production reverse proxy/deploy setup.

async function parseJsonOrThrow(response) {
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? body.message ?? JSON.stringify(body)
    } catch {
      // response had no JSON body; fall back to statusText
    }
    throw new Error(`Request failed (${response.status}): ${detail}`)
  }
  return response.json()
}

/**
 * Check backend health.
 * @returns {Promise<unknown>}
 */
export async function checkHealth() {
  const response = await fetch('/healthz')
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
  if (context !== undefined) {
    formData.append(
      'context',
      typeof context === 'string' ? context : JSON.stringify(context),
    )
  }
  for (const image of images) {
    formData.append('images', image)
  }

  const response = await fetch('/api/identify', {
    method: 'POST',
    body: formData,
  })
  return parseJsonOrThrow(response)
}

/**
 * Request a market research report for a locked item.
 *
 * @param {{ item: unknown }} params
 * @returns {Promise<{
 *   price_range: unknown,
 *   demand: unknown,
 *   marketing_angle: string,
 *   sources: { title: string, url: string }[],
 * }>}
 */
export async function requestResearch({ item }) {
  const response = await fetch('/api/research', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item }),
  })
  return parseJsonOrThrow(response)
}

/**
 * Request generated marketplace listing content for the approved item.
 *
 * @param {{ item: unknown, research: unknown }} params
 * @returns {Promise<{
 *   facebook: { title: string, description: string },
 *   offerup: { title: string, description: string },
 * }>}
 */
export async function generateListing({ item, research }) {
  const response = await fetch('/api/listing', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item, research }),
  })
  return parseJsonOrThrow(response)
}
