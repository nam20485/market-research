import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  checkHealth,
  fillMarketplaceListing,
  generateListing,
  getPostingCapabilities,
  identifyItem,
  requestResearch,
} from '../src/api.js'

describe('api client contract', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  describe('checkHealth', () => {
    it('GETs /healthz', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => Response.json({ status: 'ok' })),
      )
      await expect(checkHealth()).resolves.toEqual({ status: 'ok' })
      expect(fetch).toHaveBeenCalledWith('/healthz')
    })
  })

  describe('identifyItem', () => {
    it('posts multipart with description, images, and context fields', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({ candidates: [], locked: false }),
        ),
      )
      const file = new File(['img'], 'chair.jpg', { type: 'image/jpeg' })
      await identifyItem({
        description: 'office chair',
        images: [file],
        context: {
          known_attributes: { color: 'black' },
          conversation: [{ role: 'user', content: 'office chair' }],
        },
      })

      const [url, options] = fetch.mock.calls[0]
      expect(url).toBe('/api/identify')
      expect(options.body).toBeInstanceOf(FormData)
      expect(options.body.get('description')).toBe('office chair')
      expect(options.body.get('known_attributes')).toBe(
        JSON.stringify({ color: 'black' }),
      )
      expect(options.body.get('conversation')).toBe(
        JSON.stringify([{ role: 'user', content: 'office chair' }]),
      )
      expect(options.body.get('images')).toBeInstanceOf(File)
    })

    it('accepts string context as known_attributes', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => Response.json({ candidates: [], locked: false })),
      )
      await identifyItem({
        description: 'x',
        context: '{"color":"red"}',
      })
      expect(fetch.mock.calls[0][1].body.get('known_attributes')).toBe(
        '{"color":"red"}',
      )
    })
  })

  describe('requestResearch', () => {
    beforeEach(() => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({
            price_range: { low: 10, high: 20 },
            demand: 'High',
            marketing_angle: 'Angle',
            sources: [],
          }),
        ),
      )
    })

    it('maps identify candidate name to flat item_name body', async () => {
      await requestResearch({
        item: {
          name: 'Widget Pro',
          brand: 'Acme',
          model: 'X1',
          attributes: { color: 'blue' },
          condition: 'good',
        },
      })

      const [url, options] = fetch.mock.calls[0]
      expect(url).toBe('/api/research')
      expect(JSON.parse(options.body)).toEqual({
        item_name: 'Widget Pro',
        brand: 'Acme',
        model: 'X1',
        attributes: { color: 'blue' },
        condition: 'good',
      })
    })

    it('prefers item_name when already present', async () => {
      await requestResearch({ item: { item_name: 'Already Named' } })
      expect(JSON.parse(fetch.mock.calls[0][1].body).item_name).toBe(
        'Already Named',
      )
    })

    it('formats FastAPI 422 detail arrays', async () => {
      fetch.mockResolvedValueOnce(
        Response.json(
          {
            detail: [
              {
                type: 'missing',
                loc: ['body', 'item_name'],
                msg: 'Field required',
              },
            ],
          },
          { status: 422, statusText: 'Unprocessable Entity' },
        ),
      )

      await expect(
        requestResearch({ item: { name: 'Widget' } }),
      ).rejects.toThrow('Request failed (422): item_name: Field required')
    })

    it('formats string detail and object detail', async () => {
      fetch.mockResolvedValueOnce(
        Response.json(
          { detail: 'nope' },
          { status: 400, statusText: 'Bad Request' },
        ),
      )
      await expect(
        requestResearch({ item: { name: 'Widget' } }),
      ).rejects.toThrow('Request failed (400): nope')

      fetch.mockResolvedValueOnce(
        Response.json(
          { detail: { code: 'x' } },
          { status: 500, statusText: 'Error' },
        ),
      )
      await expect(
        requestResearch({ item: { name: 'Widget' } }),
      ).rejects.toThrow('Request failed (500): {"code":"x"}')
    })

    it('falls back to statusText when body is not JSON', async () => {
      fetch.mockResolvedValueOnce(
        new Response('plain', { status: 503, statusText: 'Service Unavailable' }),
      )
      await expect(
        requestResearch({ item: { name: 'Widget' } }),
      ).rejects.toThrow('Request failed (503): Service Unavailable')
    })

    it('formats numeric detail via String()', async () => {
      fetch.mockResolvedValueOnce(
        Response.json({ detail: 7 }, { status: 418, statusText: "I'm a teapot" }),
      )
      await expect(
        requestResearch({ item: { name: 'Widget' } }),
      ).rejects.toThrow('Request failed (418): 7')
    })

    it('formats non-object array detail entries and message fallback', async () => {
      fetch.mockResolvedValueOnce(
        Response.json(
          { detail: [42, 'plain'] },
          { status: 422, statusText: 'Unprocessable Entity' },
        ),
      )
      await expect(
        requestResearch({ item: { name: 'Widget' } }),
      ).rejects.toThrow('Request failed (422): 42; plain')

      fetch.mockResolvedValueOnce(
        Response.json(
          { message: 'upstream' },
          { status: 502, statusText: 'Bad Gateway' },
        ),
      )
      await expect(
        requestResearch({ item: { name: 'Widget' } }),
      ).rejects.toThrow('Request failed (502): upstream')
    })

    it('rejects locked items without a name', async () => {
      await expect(requestResearch({ item: { brand: 'Acme' } })).rejects.toThrow(
        'Locked item is missing a name.',
      )
      expect(fetch).not.toHaveBeenCalled()
    })

    it('includes haggle_pct and floor_pct in the body when provided', async () => {
      await requestResearch({
        item: { item_name: 'Widget Pro' },
        haggle_pct: 0.2,
        floor_pct: 0.05,
      })
      expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
        item_name: 'Widget Pro',
        brand: null,
        model: null,
        attributes: {},
        condition: null,
        haggle_pct: 0.2,
        floor_pct: 0.05,
      })
    })

    it('omits haggle_pct and floor_pct when undefined', async () => {
      await requestResearch({ item: { item_name: 'Widget Pro' } })
      const body = JSON.parse(fetch.mock.calls[0][1].body)
      expect(body).not.toHaveProperty('haggle_pct')
      expect(body).not.toHaveProperty('floor_pct')
    })

    it('omits haggle_pct and floor_pct when explicitly null', async () => {
      await requestResearch({
        item: { item_name: 'Widget Pro' },
        haggle_pct: null,
        floor_pct: null,
      })
      const body = JSON.parse(fetch.mock.calls[0][1].body)
      expect(body).not.toHaveProperty('haggle_pct')
      expect(body).not.toHaveProperty('floor_pct')
    })

    it('sends only haggle_pct when floor_pct is omitted', async () => {
      await requestResearch({
        item: { item_name: 'Widget Pro' },
        haggle_pct: 0.25,
      })
      const body = JSON.parse(fetch.mock.calls[0][1].body)
      expect(body.haggle_pct).toBe(0.25)
      expect(body).not.toHaveProperty('floor_pct')
    })
  })

  describe('generateListing', () => {
    it('sends flat fields with research_approved and summary', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({
            facebook_marketplace: { title: 'FB', description: 'FB body' },
            offerup: { title: 'OU', description: 'OU body' },
          }),
        ),
      )

      await generateListing({
        item: { name: 'Widget Pro', brand: 'Acme' },
        research: {
          price_range: { low: 10, high: 20, summary: '$10-$20' },
          demand: 'High',
          marketing_angle: 'Highlight durability',
        },
      })

      expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
        item_name: 'Widget Pro',
        brand: 'Acme',
        model: null,
        attributes: {},
        condition: null,
        research_approved: true,
        research_summary:
          'Price: $10-$20. Demand: High. Angle: Highlight durability',
      })
    })

    it('builds summary from low/high when summary missing', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({
            facebook_marketplace: { title: 'FB', description: 'x' },
            offerup: { title: 'OU', description: 'y' },
          }),
        ),
      )
      await generateListing({
        item: { title: 'Lamp' },
        research: { price_range: { low: 5, high: 15 }, demand: 'Low' },
      })
      expect(JSON.parse(fetch.mock.calls[0][1].body).research_summary).toBe(
        'Price: 5–15. Demand: Low',
      )
    })

    it('handles string price_range and empty research', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({
            facebook_marketplace: { title: 'FB', description: 'x' },
            offerup: { title: 'OU', description: 'y' },
          }),
        ),
      )
      await generateListing({
        item: { label: 'Desk' },
        research: { price_range: 'around $50' },
      })
      expect(JSON.parse(fetch.mock.calls[0][1].body).research_summary).toBe(
        'Price: around $50',
      )

      await generateListing({ item: { name: 'Desk' }, research: null })
      expect(JSON.parse(fetch.mock.calls[1][1].body).research_summary).toBeNull()
    })

    it('prefers pricing.listing_price over price_range when both are present', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({
            facebook_marketplace: { title: 'FB', description: 'x' },
            offerup: { title: 'OU', description: 'y' },
          }),
        ),
      )
      await generateListing({
        item: { name: 'Widget Pro' },
        research: {
          price_range: { low: 10, high: 20, summary: '$10-$20' },
          pricing: { listing_price: 63.25, currency: 'USD', fmv: 55 },
          demand: 'High',
          marketing_angle: 'Highlight durability',
        },
      })
      expect(JSON.parse(fetch.mock.calls[0][1].body).research_summary).toBe(
        'Price: USD 63.25. Demand: High. Angle: Highlight durability',
      )
    })

    it('falls back to price_range when pricing is missing or incomplete', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({
            facebook_marketplace: { title: 'FB', description: 'x' },
            offerup: { title: 'OU', description: 'y' },
          }),
        ),
      )
      await generateListing({
        item: { name: 'Widget Pro' },
        research: {
          price_range: { summary: '$10-$20' },
          pricing: null,
          demand: 'High',
        },
      })
      expect(JSON.parse(fetch.mock.calls[0][1].body).research_summary).toBe(
        'Price: $10-$20. Demand: High',
      )

      await generateListing({
        item: { name: 'Widget Pro' },
        research: {
          price_range: { summary: '$5-$9' },
          pricing: { listing_price: 'not-a-number' },
          demand: 'Low',
        },
      })
      expect(JSON.parse(fetch.mock.calls[1][1].body).research_summary).toBe(
        'Price: $5-$9. Demand: Low',
      )
    })

    it('defaults pricing currency to USD when missing', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({
            facebook_marketplace: { title: 'FB', description: 'x' },
            offerup: { title: 'OU', description: 'y' },
          }),
        ),
      )
      await generateListing({
        item: { name: 'Widget Pro' },
        research: { pricing: { listing_price: 42 }, demand: 'High' },
      })
      expect(JSON.parse(fetch.mock.calls[0][1].body).research_summary).toBe(
        'Price: USD 42. Demand: High',
      )
    })
  })

  describe('getPostingCapabilities', () => {
    it('GETs /api/post/capabilities', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({
            enabled: true,
            marketplaces: [{ id: 'facebook_marketplace', label: 'Facebook Marketplace' }],
          }),
        ),
      )
      await expect(getPostingCapabilities()).resolves.toEqual({
        enabled: true,
        marketplaces: [{ id: 'facebook_marketplace', label: 'Facebook Marketplace' }],
      })
      expect(fetch).toHaveBeenCalledWith('/api/post/capabilities')
    })
  })

  describe('fillMarketplaceListing', () => {
    it('posts multipart with marketplace, title, description, price, and images', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({ status: 'filled', steps_summary: ['fill: ok'] }),
        ),
      )
      const file = new File(['img'], 'lamp.jpg', { type: 'image/jpeg' })

      await fillMarketplaceListing({
        marketplace: 'facebook_marketplace',
        listing: { title: 'Lamp', description: 'Nice lamp' },
        price: 25.5,
        images: [file],
      })

      const [url, options] = fetch.mock.calls[0]
      expect(url).toBe('/api/post/fill')
      expect(options.body).toBeInstanceOf(FormData)
      expect(options.body.get('marketplace')).toBe('facebook_marketplace')
      expect(options.body.get('title')).toBe('Lamp')
      expect(options.body.get('description')).toBe('Nice lamp')
      expect(options.body.get('price')).toBe('25.5')
      expect(options.body.get('images')).toBeInstanceOf(File)
    })

    it('omits price when undefined, null, or an empty string', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => Response.json({ status: 'filled', steps_summary: [] })),
      )

      await fillMarketplaceListing({
        marketplace: 'facebook_marketplace',
        listing: { title: 'Lamp', description: 'D' },
      })
      expect(fetch.mock.calls[0][1].body.has('price')).toBe(false)

      await fillMarketplaceListing({
        marketplace: 'facebook_marketplace',
        listing: { title: 'Lamp', description: 'D' },
        price: null,
      })
      expect(fetch.mock.calls[1][1].body.has('price')).toBe(false)

      await fillMarketplaceListing({
        marketplace: 'facebook_marketplace',
        listing: { title: 'Lamp', description: 'D' },
        price: '',
      })
      expect(fetch.mock.calls[2][1].body.has('price')).toBe(false)
    })

    it('defaults title/description to empty strings when listing fields are missing', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () => Response.json({ status: 'filled', steps_summary: [] })),
      )
      await fillMarketplaceListing({ marketplace: 'facebook_marketplace', listing: {} })
      const body = fetch.mock.calls[0][1].body
      expect(body.get('title')).toBe('')
      expect(body.get('description')).toBe('')
      expect(body.getAll('images')).toHaveLength(0)
    })

    it('surfaces backend errors via parseJsonOrThrow', async () => {
      vi.stubGlobal(
        'fetch',
        vi.fn(async () =>
          Response.json({ detail: 'Marketplace posting is disabled.' }, { status: 400 }),
        ),
      )
      await expect(
        fillMarketplaceListing({ marketplace: 'facebook_marketplace', listing: {} }),
      ).rejects.toThrow('Request failed (400): Marketplace posting is disabled.')
    })
  })
})
