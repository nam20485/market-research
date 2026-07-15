import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  checkHealth,
  generateListing,
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
  })
})
