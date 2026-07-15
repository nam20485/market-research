import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import StepIndicator from './StepIndicator.jsx'

afterEach(() => cleanup())

describe('StepIndicator', () => {
  it('marks the current step active and prior steps complete', () => {
    render(<StepIndicator currentStep="research" />)
    expect(screen.getByText('1. Identify').className).toMatch(/indigo-100/)
    expect(screen.getByText('2. Research').className).toMatch(/indigo-600/)
    expect(screen.getByText('3. Listing').className).toMatch(/gray-100/)
  })

  it('treats unknown step as none active', () => {
    render(<StepIndicator currentStep="unknown" />)
    expect(screen.getByText('1. Identify').className).toMatch(/gray-100/)
  })
})

describe('StepIndicator clickability', () => {
  it('renders all three labels', async () => {
    const user = userEvent.setup()
    render(<StepIndicator currentStep="identify" />)
    expect(screen.getByText('1. Identify')).toBeInTheDocument()
    await user.click(screen.getByText('1. Identify'))
  })
})
