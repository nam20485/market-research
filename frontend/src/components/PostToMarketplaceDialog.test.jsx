import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PostToMarketplaceDialog, { derivePrefillPrice } from './PostToMarketplaceDialog.jsx'

vi.mock('../api.js', () => ({
  fillMarketplaceListing: vi.fn(),
}))

import { fillMarketplaceListing } from '../api.js'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const listing = { title: 'FB Title', description: 'FB Desc' }

describe('derivePrefillPrice', () => {
  it('prefers pricing.listing_price when present', () => {
    const research = {
      pricing: { listing_price: 63.25, currency: 'USD' },
      price_range: { low: 10, high: 20 },
    }
    expect(derivePrefillPrice(research)).toBe(63.25)
  })

  it('falls back to price_range.low when pricing is missing', () => {
    expect(derivePrefillPrice({ price_range: { low: 10, high: 20 } })).toBe(10)
  })

  it('falls back to price_range.high when low is unusable', () => {
    expect(derivePrefillPrice({ price_range: { high: 20 } })).toBe(20)
  })

  it('falls back to blank when pricing and price_range are both unusable', () => {
    expect(derivePrefillPrice({ pricing: { listing_price: 'not-a-number' } })).toBe('')
    expect(derivePrefillPrice({})).toBe('')
    expect(derivePrefillPrice(null)).toBe('')
    expect(derivePrefillPrice(undefined)).toBe('')
  })
})

describe('PostToMarketplaceDialog', () => {
  it('prefills the price field from research.pricing.listing_price', () => {
    render(
      <PostToMarketplaceDialog
        marketplace="facebook_marketplace"
        listing={listing}
        research={{ pricing: { listing_price: 63.25 }, price_range: { low: 10 } }}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByLabelText(/price/i)).toHaveValue(63.25)
  })

  it('falls back to price_range when pricing is absent', () => {
    render(
      <PostToMarketplaceDialog
        marketplace="facebook_marketplace"
        listing={listing}
        research={{ price_range: { low: 42 } }}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByLabelText(/price/i)).toHaveValue(42)
  })

  it('leaves the price field blank when neither pricing nor price_range is usable', () => {
    render(
      <PostToMarketplaceDialog
        marketplace="facebook_marketplace"
        listing={listing}
        research={null}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByLabelText(/price/i)).toHaveValue(null)
  })

  it('walks readiness -> fill -> success and shows the step summary', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    let resolveFill
    fillMarketplaceListing.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFill = resolve
        }),
    )

    render(
      <PostToMarketplaceDialog
        marketplace="facebook_marketplace"
        listing={listing}
        research={{ pricing: { listing_price: 63.25 } }}
        photos={[{ name: 'photo.jpg' }]}
        onClose={onClose}
      />,
    )

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /ok, fill the form/i }))

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(fillMarketplaceListing).toHaveBeenCalledWith({
      marketplace: 'facebook_marketplace',
      listing,
      price: 63.25,
      images: [{ name: 'photo.jpg' }],
    })

    resolveFill({ status: 'filled', steps_summary: ['navigate_page: ok', 'fill: ok'] })

    await waitFor(() => {
      expect(screen.getByText(/review the listing there/i)).toBeInTheDocument()
    })
    expect(screen.getByText('navigate_page: ok')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /done/i }))
    expect(onClose).toHaveBeenCalled()
  })

  it('cancels from the readiness step without calling the API', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(
      <PostToMarketplaceDialog
        marketplace="facebook_marketplace"
        listing={listing}
        research={null}
        onClose={onClose}
      />,
    )
    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onClose).toHaveBeenCalled()
    expect(fillMarketplaceListing).not.toHaveBeenCalled()
  })

  it('shows an error and allows retry, sending an updated price', async () => {
    const user = userEvent.setup()
    fillMarketplaceListing
      .mockRejectedValueOnce(new Error('chrome unreachable'))
      .mockResolvedValueOnce({ status: 'filled', steps_summary: [] })

    render(
      <PostToMarketplaceDialog
        marketplace="facebook_marketplace"
        listing={listing}
        research={null}
        onClose={vi.fn()}
      />,
    )

    const priceInput = screen.getByLabelText(/price/i)
    await user.type(priceInput, '19.99')
    await user.click(screen.getByRole('button', { name: /ok, fill the form/i }))

    await waitFor(() => {
      expect(screen.getByText('chrome unreachable')).toBeInTheDocument()
    })
    expect(fillMarketplaceListing).toHaveBeenCalledWith(
      expect.objectContaining({ price: 19.99 }),
    )

    await user.click(screen.getByRole('button', { name: /retry/i }))
    await waitFor(() => {
      expect(screen.getByText(/review the listing there/i)).toBeInTheDocument()
    })
  })

  it('uses a fallback error message when the rejection has no message', async () => {
    fillMarketplaceListing.mockRejectedValueOnce({})
    const user = userEvent.setup()

    render(
      <PostToMarketplaceDialog
        marketplace="facebook_marketplace"
        listing={listing}
        research={null}
        onClose={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /ok, fill the form/i }))

    await waitFor(() => {
      expect(
        screen.getByText(/failed to fill the marketplace listing/i),
      ).toBeInTheDocument()
    })
  })

  it('omits price entirely when the field is cleared', async () => {
    const user = userEvent.setup()
    fillMarketplaceListing.mockResolvedValueOnce({ status: 'filled', steps_summary: [] })

    render(
      <PostToMarketplaceDialog
        marketplace="facebook_marketplace"
        listing={listing}
        research={{ pricing: { listing_price: 63.25 } }}
        onClose={vi.fn()}
      />,
    )

    await user.clear(screen.getByLabelText(/price/i))
    await user.click(screen.getByRole('button', { name: /ok, fill the form/i }))

    await waitFor(() => {
      expect(fillMarketplaceListing).toHaveBeenCalledWith(
        expect.objectContaining({ price: undefined }),
      )
    })
  })

  it('defaults photos to an empty array when omitted', async () => {
    const user = userEvent.setup()
    fillMarketplaceListing.mockResolvedValueOnce({ status: 'filled', steps_summary: [] })

    render(
      <PostToMarketplaceDialog
        marketplace="facebook_marketplace"
        listing={listing}
        research={null}
        onClose={vi.fn()}
      />,
    )
    await user.click(screen.getByRole('button', { name: /ok, fill the form/i }))

    await waitFor(() => {
      expect(fillMarketplaceListing).toHaveBeenCalledWith(
        expect.objectContaining({ images: [] }),
      )
    })
  })

  it('shows OfferUp-specific title and emulator readiness instructions', () => {
    render(
      <PostToMarketplaceDialog
        marketplace="offerup"
        listing={listing}
        research={null}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByRole('dialog', { name: /post to offerup/i })).toBeInTheDocument()
    expect(screen.getByText(/android emulator/i)).toBeInTheDocument()
    expect(screen.getByText(/offerup app/i)).toBeInTheDocument()
    expect(screen.queryByText(/chrome/i)).not.toBeInTheDocument()
  })

  it('shows Facebook-specific title and Chrome readiness instructions', () => {
    render(
      <PostToMarketplaceDialog
        marketplace="facebook_marketplace"
        listing={listing}
        research={null}
        onClose={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('dialog', { name: /post to facebook marketplace/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/open chrome/i)).toBeInTheDocument()
    expect(screen.getByText(/remote debugging/i)).toBeInTheDocument()
  })
})
