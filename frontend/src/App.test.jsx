import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App.jsx'

vi.mock('./api.js', () => ({
  identifyItem: vi.fn(),
  requestResearch: vi.fn(),
  generateListing: vi.fn(),
}))

import { generateListing, identifyItem, requestResearch } from './api.js'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  window.localStorage.clear()
  document.documentElement.classList.remove('dark')
})

beforeEach(() => {
  window.localStorage.setItem('theme', 'dark')
})

describe('App wizard', () => {
  it('walks identify → research → listing and can start over', async () => {
    const user = userEvent.setup()
    identifyItem.mockResolvedValue({
      candidates: [{ name: 'Widget', brand: 'Acme', confidence: 0.95 }],
      locked: true,
    })
    requestResearch.mockResolvedValue({
      price_range: { summary: '$10-$20' },
      demand: 'High',
      marketing_angle: 'Angle',
      sources: [],
    })
    generateListing.mockResolvedValue({
      facebook_marketplace: { title: 'FB', description: 'FB body' },
      offerup: { title: 'OU', description: 'OU body' },
    })

    render(<App />)

    expect(screen.getByText('Market Research Assistant')).toBeInTheDocument()
    expect(screen.getByText('1. Identify')).toBeInTheDocument()

    await user.type(screen.getByLabelText(/describe the item/i), 'a widget')
    await user.click(screen.getByRole('button', { name: /identify item/i }))
    await waitFor(() => expect(screen.getAllByText('Widget').length).toBeGreaterThan(0))
    await user.click(screen.getAllByRole('button', { name: /Widget/i }).at(-1))
    await user.click(
      screen.getByRole('button', { name: /confirm & continue to research/i }),
    )

    await waitFor(() => {
      expect(screen.getByText('Market research report')).toBeInTheDocument()
    })
    await waitFor(() => expect(screen.getByText('$10-$20')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /back to identify/i }))
    expect(screen.getByText(/identify your item/i)).toBeInTheDocument()

    await user.type(screen.getByLabelText(/describe the item/i), 'a widget again')
    await user.click(screen.getByRole('button', { name: /identify item/i }))
    await waitFor(() => expect(screen.getAllByText('Widget').length).toBeGreaterThan(0))
    await user.click(screen.getAllByRole('button', { name: /Widget/i }).at(-1))
    await user.click(
      screen.getByRole('button', { name: /confirm & continue to research/i }),
    )
    await waitFor(() => {
      expect(screen.getByText('Market research report')).toBeInTheDocument()
    })
    await waitFor(() => expect(screen.getByText('$10-$20')).toBeInTheDocument())
    await user.click(
      screen.getByRole('button', { name: /approve & continue to listing/i }),
    )

    await waitFor(() => {
      expect(screen.getByText(/your listing is ready/i)).toBeInTheDocument()
    })
    await waitFor(() => expect(screen.getByText('FB')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /back to research/i }))
    await waitFor(() => {
      expect(screen.getByText('Market research report')).toBeInTheDocument()
    })
    await user.click(
      screen.getByRole('button', { name: /approve & continue to listing/i }),
    )
    await waitFor(() => expect(screen.getByText('FB')).toBeInTheDocument())

    await user.click(
      screen.getByRole('button', { name: /start over with a new item/i }),
    )
    expect(screen.getByText(/identify your item/i)).toBeInTheDocument()
  })

  it('toggles theme between dark and light', async () => {
    const user = userEvent.setup()
    render(<App />)
    const toggle = screen.getByRole('button', { name: /switch to light mode/i })
    await user.click(toggle)
    expect(
      screen.getByRole('button', { name: /switch to dark mode/i }),
    ).toBeInTheDocument()
    expect(window.localStorage.getItem('theme')).toBe('light')
  })
})
