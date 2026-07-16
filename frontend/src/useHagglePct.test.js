import { cleanup, renderHook, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import useHagglePct, {
  DEFAULT_HAGGLE_PCT,
  MAX_HAGGLE_PCT,
  MIN_HAGGLE_PCT,
} from './useHagglePct.js'

afterEach(() => {
  cleanup()
  window.localStorage.clear()
})

describe('useHagglePct', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('defaults to DEFAULT_HAGGLE_PCT when nothing stored', () => {
    const { result } = renderHook(() => useHagglePct())
    expect(result.current.hagglePct).toBe(DEFAULT_HAGGLE_PCT)
  })

  it('restores a previously stored value', () => {
    window.localStorage.setItem('hagglePct', JSON.stringify(0.2))
    const { result } = renderHook(() => useHagglePct())
    expect(result.current.hagglePct).toBe(0.2)
  })

  it('ignores corrupt stored JSON', () => {
    window.localStorage.setItem('hagglePct', '{not json')
    const { result } = renderHook(() => useHagglePct())
    expect(result.current.hagglePct).toBe(DEFAULT_HAGGLE_PCT)
  })

  it('ignores non-numeric stored values', () => {
    window.localStorage.setItem('hagglePct', JSON.stringify('fifteen'))
    const { result } = renderHook(() => useHagglePct())
    expect(result.current.hagglePct).toBe(DEFAULT_HAGGLE_PCT)
  })

  it('ignores non-finite stored values', () => {
    window.localStorage.setItem('hagglePct', JSON.stringify(null))
    const { result } = renderHook(() => useHagglePct())
    expect(result.current.hagglePct).toBe(DEFAULT_HAGGLE_PCT)
  })

  it('updates and persists a new value', () => {
    const { result } = renderHook(() => useHagglePct())

    act(() => {
      result.current.setHagglePct(0.25)
    })

    expect(result.current.hagglePct).toBe(0.25)
    expect(JSON.parse(window.localStorage.getItem('hagglePct'))).toBe(0.25)
  })

  it('clamps values above MAX_HAGGLE_PCT', () => {
    const { result } = renderHook(() => useHagglePct())

    act(() => {
      result.current.setHagglePct(5)
    })

    expect(result.current.hagglePct).toBe(MAX_HAGGLE_PCT)
  })

  it('clamps values below MIN_HAGGLE_PCT', () => {
    const { result } = renderHook(() => useHagglePct())

    act(() => {
      result.current.setHagglePct(-1)
    })

    expect(result.current.hagglePct).toBe(MIN_HAGGLE_PCT)
  })

  it('accepts numeric strings and falls back for non-numeric input', () => {
    const { result } = renderHook(() => useHagglePct())

    act(() => {
      result.current.setHagglePct('0.3')
    })
    expect(result.current.hagglePct).toBe(0.3)

    act(() => {
      result.current.setHagglePct('not a number')
    })
    expect(result.current.hagglePct).toBe(DEFAULT_HAGGLE_PCT)
  })
})
