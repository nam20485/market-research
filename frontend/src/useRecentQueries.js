import { useCallback, useState } from 'react'

const STORAGE_KEY = 'recentQueries'
const MAX_ENTRIES = 10

function readStored() {
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((entry) => typeof entry === 'string' && entry.trim())
  } catch {
    return []
  }
}

function persist(queries) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(queries))
}

export default function useRecentQueries() {
  const [recentQueries, setRecentQueries] = useState(readStored)

  const addQuery = useCallback((text) => {
    const trimmed = text.trim()
    if (!trimmed) return
    setRecentQueries((current) => {
      const next = [trimmed, ...current.filter((entry) => entry !== trimmed)].slice(
        0,
        MAX_ENTRIES,
      )
      persist(next)
      return next
    })
  }, [])

  const clearQueries = useCallback(() => {
    persist([])
    setRecentQueries([])
  }, [])

  return { recentQueries, addQuery, clearQueries }
}
