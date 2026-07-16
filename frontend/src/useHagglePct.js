import { useCallback, useState } from 'react'

const STORAGE_KEY = 'hagglePct'

// Mirrors the backend's Settings.default_haggle_pct (app/config.py).
export const DEFAULT_HAGGLE_PCT = 0.15
export const MIN_HAGGLE_PCT = 0
export const MAX_HAGGLE_PCT = 0.5

function clamp(value) {
  return Math.min(MAX_HAGGLE_PCT, Math.max(MIN_HAGGLE_PCT, value))
}

function readStored() {
  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) return DEFAULT_HAGGLE_PCT
  try {
    const parsed = JSON.parse(raw)
    if (typeof parsed !== 'number' || !Number.isFinite(parsed)) {
      return DEFAULT_HAGGLE_PCT
    }
    return clamp(parsed)
  } catch {
    return DEFAULT_HAGGLE_PCT
  }
}

function persist(value) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
}

/**
 * Persist the user's last-used haggle percentage (0-0.5) in localStorage,
 * following the same pattern as useRecentQueries.js / useTheme.js.
 */
export default function useHagglePct() {
  const [hagglePct, setHagglePctState] = useState(readStored)

  const setHagglePct = useCallback((value) => {
    const numeric = typeof value === 'number' ? value : Number(value)
    const next = Number.isFinite(numeric) ? clamp(numeric) : DEFAULT_HAGGLE_PCT
    persist(next)
    setHagglePctState(next)
  }, [])

  return { hagglePct, setHagglePct }
}
