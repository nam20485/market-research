import { beforeEach, describe, expect, it, vi } from 'vitest'

describe('main entry', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>'
    vi.resetModules()
  })

  it('mounts App into #root', async () => {
    const render = vi.fn()
    const createRoot = vi.fn(() => ({ render }))
    vi.doMock('react-dom/client', () => ({ createRoot }))
    vi.doMock('./App.jsx', () => ({ default: () => null }))
    vi.doMock('./index.css', () => ({}))

    await import('./main.jsx')

    expect(createRoot).toHaveBeenCalled()
    expect(document.getElementById('root')).toBeTruthy()
    expect(render).toHaveBeenCalled()
  })
})
