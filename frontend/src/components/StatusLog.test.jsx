import { act, cleanup, render, screen } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import StatusLog, { itemDisplayName, useStatusLog } from './StatusLog.jsx'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('itemDisplayName', () => {
  it('prefers brand + model/name and falls back', () => {
    expect(itemDisplayName({ brand: 'Acme', model: 'X1' })).toBe('Acme X1')
    expect(itemDisplayName({ name: 'Widget' })).toBe('Widget')
    expect(itemDisplayName({ item_name: 'Thing' })).toBe('Thing')
    expect(itemDisplayName({ title: 'Titled' })).toBe('Titled')
    expect(itemDisplayName({})).toBe('item')
    expect(itemDisplayName(null)).toBe('item')
  })
})

describe('StatusLog', () => {
  it('renders active dots and completed result verbs', () => {
    render(
      <StatusLog
        lines={[
          { id: '0', label: 'Searching Widget', state: 'done', result: 'done' },
          { id: '1', label: 'Writing report', state: 'active' },
          { id: '2', label: 'Silent done', state: 'done' },
          { id: '3', label: 'Silent fail', state: 'failed' },
        ]}
      />,
    )
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('Searching Widget')).toBeInTheDocument()
    expect(screen.getAllByText('done').length).toBeGreaterThan(0)
    expect(screen.getByText('Writing report')).toBeInTheDocument()
    expect(screen.getByText('failed')).toBeInTheDocument()
  })

  it('renders failed result styling', () => {
    render(
      <StatusLog
        lines={[{ id: '0', label: 'Request', state: 'failed', result: 'failed' }]}
      />,
    )
    expect(screen.getByText('failed')).toBeInTheDocument()
  })

  it('renders nothing when empty', () => {
    const { container } = render(<StatusLog lines={[]} />)
    expect(container).toBeEmptyDOMElement()
    const { container: missing } = render(<StatusLog />)
    expect(missing).toBeEmptyDOMElement()
  })
})

function HookHarness({ stages, apiRef, autoStart = true }) {
  const api = useStatusLog({ advanceMs: 1000 })
  useEffect(() => {
    apiRef.current = api
    if (autoStart) api.start(stages)
    // Intentionally run once on mount for the test harness.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return <StatusLog lines={api.lines} />
}

describe('useStatusLog', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  it('advances stages on the interval and finishes with complete', async () => {
    const apiRef = { current: null }
    render(<HookHarness stages={['One', 'Two']} apiRef={apiRef} />)

    expect(screen.getByText('One')).toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(screen.getByText('Two')).toBeInTheDocument()
    expect(screen.getByText('done')).toBeInTheDocument()

    // Extra tick past the last stage is a no-op.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(screen.getByText('Two')).toBeInTheDocument()

    await act(async () => {
      apiRef.current.finish('complete')
    })
    expect(screen.getByText('complete')).toBeInTheDocument()
  })

  it('marks the active line failed', async () => {
    const apiRef = { current: null }
    render(<HookHarness stages={['Working']} apiRef={apiRef} />)
    await act(async () => {
      apiRef.current.fail('failed')
    })
    expect(screen.getByText('failed')).toBeInTheDocument()
  })

  it('handles empty stages, reset, and fail with no lines', async () => {
    const apiRef = { current: null }
    const { container } = render(
      <HookHarness stages={[]} apiRef={apiRef} autoStart={false} />,
    )
    await act(async () => {
      apiRef.current.start([])
      apiRef.current.finish('complete')
      apiRef.current.fail('failed')
    })
    expect(screen.getByText('Request')).toBeInTheDocument()
    expect(screen.getByText('failed')).toBeInTheDocument()

    await act(async () => {
      apiRef.current.reset()
    })
    expect(container.querySelector('[role="status"]')).toBeNull()
  })
})
