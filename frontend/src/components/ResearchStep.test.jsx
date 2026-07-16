import { cleanup, render, screen, waitFor } from '@testing-library/react'
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
      expect(screen.getByText('Unknown')).toBeInTheDocument()
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
})
