import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ListingStep from './ListingStep.jsx'

vi.mock('../api.js', () => ({
  generateListing: vi.fn(),
  getPostingCapabilities: vi.fn(),
  fillMarketplaceListing: vi.fn(),
}))

import { fillMarketplaceListing, generateListing, getPostingCapabilities } from '../api.js'

function stubClipboard(writeText) {
  vi.stubGlobal('navigator', {
    ...globalThis.navigator,
    clipboard: { writeText },
  })
}

beforeEach(() => {
  getPostingCapabilities.mockResolvedValue({ enabled: false, marketplaces: [] })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

const item = { name: 'Widget' }
const research = { demand: 'High', marketing_angle: 'A' }

describe('ListingStep', () => {
  it('renders marketplace listings and copies to clipboard', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    stubClipboard(writeText)

    generateListing.mockResolvedValue({
      facebook_marketplace: { title: 'FB Title', description: 'FB Desc' },
      offerup: { title: 'OU Title', description: 'OU Desc' },
    })

    const onBack = vi.fn()
    const onStartOver = vi.fn()
    render(
      <ListingStep
        item={item}
        research={research}
        onBack={onBack}
        onStartOver={onStartOver}
      />,
    )

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(
      screen.getByText(/drafting facebook marketplace listing for widget/i),
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('FB Title')).toBeInTheDocument()
    })
    expect(screen.getByText(/complete/i)).toBeInTheDocument()
    expect(screen.getByText('OU Title')).toBeInTheDocument()

    const copyButtons = screen.getAllByRole('button', {
      name: /copy to clipboard/i,
    })
    await user.click(copyButtons[0])
    expect(writeText).toHaveBeenCalledWith('FB Title\n\nFB Desc')
    await waitFor(() => {
      expect(screen.getByText('Copied!')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /back to research/i }))
    expect(onBack).toHaveBeenCalled()
    await user.click(
      screen.getByRole('button', { name: /start over with a new item/i }),
    )
    expect(onStartOver).toHaveBeenCalled()
  })

  it('shows error and retries; handles clipboard failure', async () => {
    const user = userEvent.setup()
    stubClipboard(vi.fn().mockRejectedValue(new Error('denied')))

    generateListing
      .mockRejectedValueOnce(new Error('listing failed'))
      .mockResolvedValueOnce({
        facebook_marketplace: { title: 'FB', description: 'D' },
        offerup: { title: 'OU', description: 'D2' },
      })

    render(
      <ListingStep
        item={item}
        research={research}
        onBack={vi.fn()}
        onStartOver={vi.fn()}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText(/listing failed/i)).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /retry/i }))
    await waitFor(() => {
      expect(screen.getByText('FB')).toBeInTheDocument()
    })

    await user.click(
      screen.getAllByRole('button', { name: /copy to clipboard/i })[0],
    )
    expect(screen.queryByText('Copied!')).not.toBeInTheDocument()
  })

  it('uses fallback error text when rejection has no message', async () => {
    const user = userEvent.setup()
    stubClipboard(vi.fn())
    generateListing.mockRejectedValueOnce({})

    render(
      <ListingStep
        item={item}
        research={research}
        onBack={vi.fn()}
        onStartOver={vi.fn()}
      />,
    )

    await waitFor(() => {
      expect(
        screen.getByText(/failed to generate listing content/i),
      ).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /retry/i }))
  })

  it('hides the post-to-Facebook button when posting capabilities are disabled', async () => {
    generateListing.mockResolvedValue({
      facebook_marketplace: { title: 'FB', description: 'D' },
      offerup: { title: 'OU', description: 'D2' },
    })

    render(
      <ListingStep item={item} research={research} onBack={vi.fn()} onStartOver={vi.fn()} />,
    )

    await waitFor(() => {
      expect(screen.getByText('FB')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('button', { name: /post to facebook marketplace/i }),
    ).not.toBeInTheDocument()
  })

  it('hides the post-to-Facebook button when the FB marketplace is not in capabilities', async () => {
    getPostingCapabilities.mockResolvedValue({
      enabled: true,
      marketplaces: [{ id: 'offerup', label: 'OfferUp' }],
    })
    generateListing.mockResolvedValue({
      facebook_marketplace: { title: 'FB', description: 'D' },
      offerup: { title: 'OU', description: 'D2' },
    })

    render(
      <ListingStep item={item} research={research} onBack={vi.fn()} onStartOver={vi.fn()} />,
    )

    await waitFor(() => {
      expect(screen.getByText('FB')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('button', { name: /post to facebook marketplace/i }),
    ).not.toBeInTheDocument()
  })

  it('shows the post-to-Facebook button, opens the dialog, and closes it', async () => {
    const user = userEvent.setup()
    getPostingCapabilities.mockResolvedValue({
      enabled: true,
      marketplaces: [{ id: 'facebook_marketplace', label: 'Facebook Marketplace' }],
    })
    generateListing.mockResolvedValue({
      facebook_marketplace: { title: 'FB', description: 'D' },
      offerup: { title: 'OU', description: 'D2' },
    })

    render(
      <ListingStep
        item={item}
        research={{ ...research, pricing: { listing_price: 63.25 } }}
        photos={[{ name: 'photo.jpg' }]}
        onBack={vi.fn()}
        onStartOver={vi.fn()}
      />,
    )

    const postButton = await screen.findByRole('button', {
      name: /post to facebook marketplace/i,
    })
    await user.click(postButton)

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByLabelText(/price/i)).toHaveValue(63.25)

    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(fillMarketplaceListing).not.toHaveBeenCalled()
  })

  it('does not fail when capabilities fetch rejects', async () => {
    getPostingCapabilities.mockRejectedValue(new Error('offline'))
    generateListing.mockResolvedValue({
      facebook_marketplace: { title: 'FB', description: 'D' },
      offerup: { title: 'OU', description: 'D2' },
    })

    render(
      <ListingStep item={item} research={research} onBack={vi.fn()} onStartOver={vi.fn()} />,
    )

    await waitFor(() => {
      expect(screen.getByText('FB')).toBeInTheDocument()
    })
    expect(
      screen.queryByRole('button', { name: /post to facebook marketplace/i }),
    ).not.toBeInTheDocument()
  })
})
