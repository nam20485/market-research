import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import IdentifyStep from './IdentifyStep.jsx'

vi.mock('../api.js', () => ({
  identifyItem: vi.fn(),
}))

import { identifyItem } from '../api.js'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:preview')
  URL.revokeObjectURL = vi.fn()
})

describe('IdentifyStep', () => {
  it('requires description or photo before submit', async () => {
    const user = userEvent.setup()
    render(<IdentifyStep onLocked={vi.fn()} />)
    await user.click(screen.getByRole('button', { name: /identify item/i }))
    expect(
      screen.getByText(/add a description or at least one photo/i),
    ).toBeInTheDocument()
    expect(identifyItem).not.toHaveBeenCalled()
  })

  it('submits description, shows candidates, and locks selection', async () => {
    const user = userEvent.setup()
    const onLocked = vi.fn()
    identifyItem.mockResolvedValue({
      candidates: [
        {
          name: 'Aeron',
          brand: 'Herman Miller',
          model: 'Aeron',
          confidence: 0.9,
          summary: 'Mesh chair',
        },
        {
          title: 'Other chair',
          confidence_score: 'likely',
          description: 'Different',
        },
      ],
      locked: true,
      context: { known_attributes: {}, conversation: [] },
    })

    render(<IdentifyStep onLocked={onLocked} />)
    await user.type(
      screen.getByLabelText(/describe the item/i),
      'black office chair',
    )
    await user.click(screen.getByRole('button', { name: /identify item/i }))

    await waitFor(() => {
      expect(screen.getAllByText('Aeron').length).toBeGreaterThan(0)
    })
    expect(screen.getByText(/item identified with high confidence/i)).toBeInTheDocument()
    expect(screen.getAllByText('90% match').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Other chair').length).toBeGreaterThan(0)

    await user.click(screen.getAllByRole('button', { name: /Aeron/i }).at(-1))
    await user.click(
      screen.getByRole('button', { name: /confirm & continue to research/i }),
    )
    expect(onLocked).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Aeron' }),
      expect.any(Object),
    )
  })

  it('shows manual lock messaging when not locked and handles API errors', async () => {
    const user = userEvent.setup()
    identifyItem.mockResolvedValueOnce({
      candidates: [
        { name: 'Guess', brand: 'X', model: 'Y' },
        { name: 'Other', brand: 'Z', model: '1' },
      ],
      locked: false,
    })

    render(<IdentifyStep onLocked={vi.fn()} />)
    await user.type(screen.getByLabelText(/describe the item/i), 'chair')
    await user.click(screen.getByRole('button', { name: /identify item/i }))

    await waitFor(() => {
      expect(screen.getByText(/not confident yet/i)).toBeInTheDocument()
    })
    const lockButton = screen.getByRole('button', {
      name: /lock this item anyway/i,
    })
    expect(lockButton).toBeDisabled()

    const guessButtons = screen.getAllByRole('button', { name: /Guess/i })
    await user.click(guessButtons[guessButtons.length - 1])
    expect(lockButton).toBeEnabled()

    identifyItem.mockRejectedValueOnce(new Error('identify down'))
    await user.type(screen.getByLabelText(/add more details/i), ' more')
    await user.click(
      screen.getByRole('button', { name: /resubmit with more details/i }),
    )
    await waitFor(() => {
      expect(screen.getByText('identify down')).toBeInTheDocument()
    })
  })

  it('supports photo upload, remove, and submit with photos', async () => {
    const user = userEvent.setup()
    identifyItem.mockResolvedValue({ candidates: [], locked: false })
    render(<IdentifyStep onLocked={vi.fn()} />)

    const file = new File(['abc'], 'photo.png', { type: 'image/png' })
    const input = screen.getByLabelText(/photos/i)
    await user.upload(input, file)

    expect(screen.getByAltText('photo.png')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /identify item/i }))
    await waitFor(() => {
      expect(identifyItem).toHaveBeenCalled()
    })
    expect(identifyItem.mock.calls[0][0].images).toHaveLength(1)

    await user.upload(input, new File(['x'], 'keep.png', { type: 'image/png' }))
    expect(screen.getByAltText('keep.png')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /remove keep.png/i }))
    expect(screen.queryByAltText('keep.png')).not.toBeInTheDocument()
  })
})
