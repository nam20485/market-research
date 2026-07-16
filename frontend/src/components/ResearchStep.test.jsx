import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ResearchStep from './ResearchStep.jsx'

vi.mock('../api.js', () => ({
  requestResearch: vi.fn(),
}))

import { requestResearch } from '../api.js'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  window.localStorage.clear()
})

const item = { name: 'Widget', brand: 'Acme' }

describe('ResearchStep', () => {
  it('loads report, formats price summary, and approves', async () => {
    const user = userEvent.setup()
    const onApprove = vi.fn()
    const onBack = vi.fn()
    requestResearch.mockResolvedValue({
      price_range: { summary: '$10-$20' },
      demand: 'High',
      marketing_angle: 'Sell the durability',
      sources: [{ title: 'Comp A', url: 'https://example.com/a' }],
    })

    render(
      <ResearchStep item={item} onApprove={onApprove} onBack={onBack} />,
    )

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText(/item identified: acme widget/i)).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('$10-$20')).toBeInTheDocument()
    })
    expect(screen.getByText(/complete/i)).toBeInTheDocument()
    expect(screen.getByText('High')).toBeInTheDocument()
    expect(screen.getByText('Sell the durability')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Comp A' })).toHaveAttribute(
      'href',
      'https://example.com/a',
    )

    await user.click(screen.getByRole('button', { name: /back to identify/i }))
    expect(onBack).toHaveBeenCalled()

    await user.click(
      screen.getByRole('button', { name: /approve & continue to listing/i }),
    )
    expect(onApprove).toHaveBeenCalledWith(
      expect.objectContaining({ demand: 'High' }),
    )
  })

  it('formats low/high price ranges and object demand; empty sources', async () => {
    requestResearch.mockResolvedValue({
      price_range: { low: 5, high: 9, currency: 'EUR' },
      demand: { level: 'medium' },
      marketing_angle: 'Angle',
      sources: [],
    })

    render(<ResearchStep item={item} onApprove={vi.fn()} onBack={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('EUR 5 – 9')).toBeInTheDocument()
    })
    expect(screen.getByText('{"level":"medium"}')).toBeInTheDocument()
    expect(screen.getByText(/no sources returned/i)).toBeInTheDocument()
  })

  it('formats string and array price ranges', async () => {
    requestResearch.mockResolvedValue({
      price_range: 'about $40',
      demand: 'Low',
      marketing_angle: 'A',
      sources: [],
    })
    const { rerender } = render(
      <ResearchStep item={item} onApprove={vi.fn()} onBack={vi.fn()} />,
    )
    await waitFor(() => {
      expect(screen.getByText('about $40')).toBeInTheDocument()
    })

    requestResearch.mockResolvedValue({
      price_range: [10, 20],
      demand: 'Low',
      marketing_angle: 'A',
      sources: [],
    })
    rerender(
      <ResearchStep item={{ name: 'B' }} onApprove={vi.fn()} onBack={vi.fn()} />,
    )
    await waitFor(() => {
      expect(screen.getByText('10 – 20')).toBeInTheDocument()
    })
  })

  it('shows error with retry', async () => {
    const user = userEvent.setup()
    requestResearch
      .mockRejectedValueOnce(new Error('research failed'))
      .mockResolvedValueOnce({
        price_range: null,
        demand: 'Ok',
        marketing_angle: 'A',
        sources: [],
      })

    render(<ResearchStep item={item} onApprove={vi.fn()} onBack={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText(/research failed/i)).toBeInTheDocument()
    })
    await user.click(screen.getByRole('button', { name: /retry/i }))
    await waitFor(() => {
      expect(screen.getAllByText('Unknown').length).toBeGreaterThan(0)
    })
  })

  it('shows fallback research error when rejection has no message', async () => {
    requestResearch.mockRejectedValueOnce({})
    render(<ResearchStep item={item} onApprove={vi.fn()} onBack={vi.fn()} />)
    await waitFor(() => {
      expect(
        screen.getByText(/failed to generate the market research report/i),
      ).toBeInTheDocument()
    })
  })

  it('sends the default haggle_pct (15%) on the initial request', async () => {
    requestResearch.mockResolvedValue({
      price_range: { summary: '$10-$20' },
      demand: 'High',
      marketing_angle: 'Angle',
      sources: [],
      pricing: null,
    })

    render(<ResearchStep item={item} onApprove={vi.fn()} onBack={vi.fn()} />)

    await waitFor(() => {
      expect(requestResearch).toHaveBeenCalledWith(
        expect.objectContaining({ haggle_pct: 0.15 }),
      )
    })
  })

  describe.each([
    ['sold_comps', 'Based on sold comps'],
    ['asking_price', 'Based on asking prices'],
    ['unknown', 'Low confidence'],
  ])('pricing card with confidence=%s', (confidence, badgeLabel) => {
    it(`renders listing/FMV/firm-bottom prices and the "${badgeLabel}" badge`, async () => {
      requestResearch.mockResolvedValue({
        price_range: { summary: '$10-$20' },
        demand: 'High',
        marketing_angle: 'Angle',
        sources: [],
        pricing: {
          fmv: 55,
          listing_price: 63.25,
          firm_bottom: 49.5,
          currency: 'USD',
          haggle_pct: 0.15,
          floor_pct: 0.1,
          condition_multiplier: 1,
          confidence,
          rationale: null,
        },
      })

      render(<ResearchStep item={item} onApprove={vi.fn()} onBack={vi.fn()} />)

      await waitFor(() => {
        expect(screen.getByText(badgeLabel)).toBeInTheDocument()
      })
      expect(screen.getByText('Listing price')).toBeInTheDocument()
      expect(screen.getByText('USD 63.25')).toBeInTheDocument()
      expect(screen.getByText('Fair market value')).toBeInTheDocument()
      expect(screen.getByText('USD 55.00')).toBeInTheDocument()
      expect(screen.getByText('Firm bottom price')).toBeInTheDocument()
      expect(screen.getByText('USD 49.50')).toBeInTheDocument()
    })
  })

  it('renders a graceful "Unknown" pricing card when pricing is explicitly null', async () => {
    requestResearch.mockResolvedValue({
      price_range: { summary: '$10-$20' },
      demand: 'High',
      marketing_angle: 'Angle',
      sources: [],
      pricing: null,
    })

    render(<ResearchStep item={item} onApprove={vi.fn()} onBack={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Pricing strategy')).toBeInTheDocument()
    })
    expect(screen.getByText('Unknown')).toBeInTheDocument()
    expect(screen.queryByText('Listing price')).not.toBeInTheDocument()
  })

  it('renders a graceful "Unknown" pricing card when pricing is absent entirely', async () => {
    requestResearch.mockResolvedValue({
      price_range: { summary: '$5-$9' },
      demand: 'Low',
      marketing_angle: 'Angle',
      sources: [],
    })

    render(<ResearchStep item={item} onApprove={vi.fn()} onBack={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('Pricing strategy')).toBeInTheDocument()
    })
    expect(screen.getByText('Unknown')).toBeInTheDocument()
    expect(screen.queryByText('Listing price')).not.toBeInTheDocument()
  })

  it('lets the user override the haggle % and re-runs research with the new value', async () => {
    requestResearch.mockResolvedValue({
      price_range: { summary: '$10-$20' },
      demand: 'High',
      marketing_angle: 'Angle',
      sources: [],
      pricing: {
        fmv: 55,
        listing_price: 63.25,
        firm_bottom: 49.5,
        currency: 'USD',
        confidence: 'sold_comps',
      },
    })

    render(<ResearchStep item={item} onApprove={vi.fn()} onBack={vi.fn()} />)

    await waitFor(() => {
      expect(screen.getByText('USD 63.25')).toBeInTheDocument()
    })
    expect(requestResearch).toHaveBeenCalledWith(
      expect.objectContaining({ haggle_pct: 0.15 }),
    )

    const haggleInput = screen.getByLabelText(/haggle room/i)
    expect(haggleInput).toHaveValue(15)

    fireEvent.change(haggleInput, { target: { value: '20' } })

    await waitFor(() => {
      expect(requestResearch).toHaveBeenLastCalledWith(
        expect.objectContaining({ haggle_pct: 0.2 }),
      )
    })
    expect(JSON.parse(window.localStorage.getItem('hagglePct'))).toBe(0.2)
  })
})
