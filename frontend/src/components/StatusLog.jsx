import { useCallback, useEffect, useRef, useState } from 'react'
import { logger } from '../logger.js'

/**
 * Animated trailing dots for an in-progress status line.
 * @param {{ active: boolean }} props
 */
function TrailingDots({ active }) {
  const [count, setCount] = useState(3)

  useEffect(() => {
    if (!active) return undefined
    const id = window.setInterval(() => {
      setCount((current) => (current >= 10 ? 3 : current + 1))
    }, 350)
    return () => window.clearInterval(id)
  }, [active])

  return <span aria-hidden="true">{'.'.repeat(count)}</span>
}

/**
 * Shows progressive status lines while a long request is in flight.
 * Completed lines end with a result verb ("done" / "complete" / "failed").
 *
 * @param {{
 *   lines: Array<{ id: string, label: string, state: 'active' | 'done' | 'failed', result?: string }>,
 * }} props
 */
export default function StatusLog({ lines }) {
  if (!lines?.length) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="rounded-lg border border-indigo-100 bg-indigo-50/70 px-4 py-3 font-mono text-sm text-indigo-950 dark:border-indigo-900 dark:bg-indigo-950/40 dark:text-indigo-100"
    >
      <ul className="flex flex-col gap-1.5">
        {lines.map((line) => (
          <li key={line.id} className="leading-snug">
            <span>{line.label}</span>
            {line.state === 'active' ? (
              <TrailingDots active />
            ) : (
              <>
                <span aria-hidden="true">........</span>{' '}
                <span
                  className={
                    line.state === 'failed'
                      ? 'font-semibold text-red-700 dark:text-red-300'
                      : 'font-semibold text-indigo-700 dark:text-indigo-300'
                  }
                >
                  {line.result ?? (line.state === 'failed' ? 'failed' : 'done')}
                </span>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * Drive a StatusLog through staged labels while an async operation runs.
 * Stages auto-advance on an interval so the UI stays alive during long pauses;
 * when the promise settles, remaining lines are marked complete (or failed).
 *
 * @param {{ advanceMs?: number }} [options]
 */
export function useStatusLog({ advanceMs = 2800 } = {}) {
  const [lines, setLines] = useState([])
  const stagesRef = useRef([])
  const indexRef = useRef(0)
  const timerRef = useRef(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const reset = useCallback(() => {
    clearTimer()
    stagesRef.current = []
    indexRef.current = 0
    setLines([])
  }, [clearTimer])

  const start = useCallback(
    (stages) => {
      clearTimer()
      const normalized = stages.filter(Boolean)
      stagesRef.current = normalized
      indexRef.current = 0
      if (normalized.length === 0) {
        setLines([])
        return
      }
      logger.info('status:', normalized[0])
      setLines([{ id: '0', label: normalized[0], state: 'active' }])
      timerRef.current = window.setInterval(() => {
        setLines((current) => {
          const nextIndex = indexRef.current + 1
          if (nextIndex >= stagesRef.current.length) {
            return current
          }
          const updated = current.map((line, i) =>
            i === indexRef.current
              ? { ...line, state: 'done', result: 'done' }
              : line,
          )
          indexRef.current = nextIndex
          const nextLabel = stagesRef.current[nextIndex]
          logger.info('status:', nextLabel)
          return [
            ...updated,
            { id: String(nextIndex), label: nextLabel, state: 'active' },
          ]
        })
      }, advanceMs)
    },
    [advanceMs, clearTimer],
  )

  const finish = useCallback(
    (result = 'complete') => {
      clearTimer()
      setLines((current) => {
        if (current.length === 0) return current
        return current.map((line) =>
          line.state === 'active'
            ? { ...line, state: 'done', result }
            : line,
        )
      })
      logger.info('status finished:', result)
    },
    [clearTimer],
  )

  const fail = useCallback(
    (result = 'failed') => {
      clearTimer()
      setLines((current) => {
        if (current.length === 0) {
          return [{ id: '0', label: 'Request', state: 'failed', result }]
        }
        return current.map((line) =>
          line.state === 'active'
            ? { ...line, state: 'failed', result }
            : line,
        )
      })
      logger.warn('status failed:', result)
    },
    [clearTimer],
  )

  useEffect(() => () => clearTimer(), [clearTimer])

  return { lines, start, finish, fail, reset }
}

/**
 * Build a short human label for a locked item.
 * @param {Record<string, unknown> | null | undefined} item
 * @returns {string}
 */
export function itemDisplayName(item) {
  if (!item || typeof item !== 'object') return 'item'
  const parts = [
    typeof item.brand === 'string' ? item.brand : null,
    typeof item.model === 'string'
      ? item.model
      : typeof item.name === 'string'
        ? item.name
        : typeof item.item_name === 'string'
          ? item.item_name
          : typeof item.title === 'string'
            ? item.title
            : null,
  ].filter(Boolean)
  return parts.length ? parts.join(' ') : 'item'
}
