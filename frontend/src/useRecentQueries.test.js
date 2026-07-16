import { cleanup, renderHook, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import useRecentQueries from './useRecentQueries.js'

afterEach(() => {
  cleanup()
  window.localStorage.clear()
})

describe('useRecentQueries', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('defaults to an empty list when nothing stored', () => {
    const { result } = renderHook(() => useRecentQueries())
    expect(result.current.recentQueries).toEqual([])
  })

  it('restores a previously stored list', () => {
    window.localStorage.setItem('recentQueries', JSON.stringify(['old query']))
    const { result } = renderHook(() => useRecentQueries())
    expect(result.current.recentQueries).toEqual(['old query'])
  })

  it('ignores corrupt stored JSON', () => {
    window.localStorage.setItem('recentQueries', '{not json')
    const { result } = renderHook(() => useRecentQueries())
    expect(result.current.recentQueries).toEqual([])
  })

  it('adds a query to the front of the list and persists it', () => {
    const { result } = renderHook(() => useRecentQueries())

    act(() => {
      result.current.addQuery('black office chair')
    })

    expect(result.current.recentQueries).toEqual(['black office chair'])
    expect(JSON.parse(window.localStorage.getItem('recentQueries'))).toEqual([
      'black office chair',
    ])
  })

  it('ignores blank or whitespace-only queries', () => {
    const { result } = renderHook(() => useRecentQueries())

    act(() => {
      result.current.addQuery('   ')
    })

    expect(result.current.recentQueries).toEqual([])
  })

  it('trims whitespace before storing', () => {
    const { result } = renderHook(() => useRecentQueries())

    act(() => {
      result.current.addQuery('  leather sofa  ')
    })

    expect(result.current.recentQueries).toEqual(['leather sofa'])
  })

  it('de-duplicates by moving an existing entry to the front', () => {
    const { result } = renderHook(() => useRecentQueries())

    act(() => {
      result.current.addQuery('vintage lamp')
    })
    act(() => {
      result.current.addQuery('desk fan')
    })
    act(() => {
      result.current.addQuery('vintage lamp')
    })

    expect(result.current.recentQueries).toEqual(['vintage lamp', 'desk fan'])
  })

  it('caps the list at 10 most-recent entries', () => {
    const { result } = renderHook(() => useRecentQueries())

    act(() => {
      for (let i = 0; i < 12; i += 1) {
        result.current.addQuery(`query ${i}`)
      }
    })

    expect(result.current.recentQueries).toHaveLength(10)
    expect(result.current.recentQueries[0]).toBe('query 11')
    expect(result.current.recentQueries.at(-1)).toBe('query 2')
  })

  it('clears the list and persisted storage', () => {
    const { result } = renderHook(() => useRecentQueries())

    act(() => {
      result.current.addQuery('rare coin')
    })
    act(() => {
      result.current.clearQueries()
    })

    expect(result.current.recentQueries).toEqual([])
    expect(JSON.parse(window.localStorage.getItem('recentQueries'))).toEqual([])
  })
})
