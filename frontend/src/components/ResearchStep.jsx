import { useCallback, useEffect, useState } from 'react'
import { requestResearch } from '../api.js'
import { logger } from '../logger.js'
import useHagglePct, { MAX_HAGGLE_PCT, MIN_HAGGLE_PCT } from '../useHagglePct.js'
import StatusLog, { itemDisplayName, useStatusLog } from './StatusLog.jsx'

function formatPriceRange(priceRange) {
  if (priceRange === null || priceRange === undefined) return 'Unknown'
  if (typeof priceRange === 'string') return priceRange
  if (Array.isArray(priceRange)) return priceRange.join(' – ')
  if (typeof priceRange === 'object') {
    if (priceRange.summary) return priceRange.summary
    const low = priceRange.low ?? priceRange.min
    const high = priceRange.high ?? priceRange.max
    const currency = priceRange.currency ?? 'USD'
    if (low !== undefined && high !== undefined) {
      return `${currency} ${low} – ${high}`
    }
  }
  return JSON.stringify(priceRange)
}

/**
 * Format a currency amount for display, falling back to "Unknown" when the
 * value isn't a finite number.
 * @param {unknown} amount
 * @param {string} currency
 * @returns {string}
 */
function formatAmount(amount, currency) {
  if (typeof amount !== 'number' || !Number.isFinite(amount)) return 'Unknown'
  return `${currency} ${amount.toFixed(2)}`
}

const CONFIDENCE_LABELS = {
  sold_comps: 'Based on sold comps',
  asking_price: 'Based on asking prices',
  unknown: 'Low confidence',
}

/**
 * Map a pricing confidence value to a human-readable badge label.
 * @param {unknown} confidence
 * @returns {string}
 */
function confidenceLabel(confidence) {
  return CONFIDENCE_LABELS[confidence] ?? CONFIDENCE_LABELS.unknown
}

function PricingCard({ pricing }) {
  if (!pricing || typeof pricing !== 'object') {
    return (
      <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
          Pricing strategy
        </p>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">Unknown</p>
      </div>
    )
  }

  const currency = typeof pricing.currency === 'string' ? pricing.currency : 'USD'

  return (
    <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
          Pricing strategy
        </p>
        <span className="whitespace-nowrap rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300">
          {confidenceLabel(pricing.confidence)}
        </span>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Listing price</p>
          <p className="mt-0.5 text-lg font-semibold text-gray-900 dark:text-gray-50">
            {formatAmount(pricing.listing_price, currency)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Fair market value</p>
          <p className="mt-0.5 text-lg font-semibold text-gray-900 dark:text-gray-50">
            {formatAmount(pricing.fmv, currency)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400">Firm bottom price</p>
          <p className="mt-0.5 text-lg font-semibold text-gray-900 dark:text-gray-50">
            {formatAmount(pricing.firm_bottom, currency)}
          </p>
        </div>
      </div>
      {pricing.rationale && (
        <p className="mt-3 text-sm text-gray-600 dark:text-gray-300">{pricing.rationale}</p>
      )}
    </div>
  )
}

export default function ResearchStep({ item, onApprove, onBack }) {
  const [report, setReport] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const { hagglePct, setHagglePct } = useHagglePct()
  const { lines: statusLines, start: startStatus, finish: finishStatus, fail: failStatus, reset: resetStatus } =
    useStatusLog()

  const runResearch = useCallback(
    async (haggleOverride) => {
      setIsLoading(true)
      setError(null)
      setReport(null)
      resetStatus()
      const label = itemDisplayName(item)
      startStatus([
        `Item identified: ${label}`,
        `Searching comparable listings for ${label}`,
        `Analyzing prices for ${label}`,
        `Writing research report`,
      ])
      try {
        const result = await requestResearch({
          item,
          haggle_pct: haggleOverride ?? hagglePct,
        })
        finishStatus('complete')
        logger.info('research response', {
          sources: result.sources?.length ?? 0,
        })
        setReport(result)
      } catch (err) {
        failStatus('failed')
        logger.error('research failed', err)
        setError(err.message ?? 'Failed to generate the market research report.')
      } finally {
        setIsLoading(false)
      }
    },
    [item, hagglePct, finishStatus, failStatus, resetStatus, startStatus],
  )

  // Auto-run once per item; haggle-% re-runs are triggered explicitly via
  // handleHaggleChange below (runResearch's identity also changes with
  // hagglePct, so it's intentionally excluded from these deps).
  useEffect(() => {
    runResearch()
  }, [item])

  function handleHaggleChange(event) {
    const value = Number(event.target.value) / 100
    setHagglePct(value)
    runResearch(value)
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-50">
          Market research report
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Pricing, demand, and marketing guidance based on current comparable
          listings.
        </p>
      </div>

      {(isLoading || statusLines.length > 0) && <StatusLog lines={statusLines} />}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
          <button
            type="button"
            onClick={() => runResearch()}
            className="ml-3 font-medium underline"
          >
            Retry
          </button>
        </div>
      )}

      {!isLoading && report && (
        <div className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
                Price range
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-50">
                {formatPriceRange(report.price_range)}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
                Demand
              </p>
              <p className="mt-1 text-lg font-semibold text-gray-900 dark:text-gray-50">
                {typeof report.demand === 'string'
                  ? report.demand
                  : JSON.stringify(report.demand)}
              </p>
            </div>
          </div>

          <PricingCard pricing={report.pricing} />

          <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
            <label
              htmlFor="haggle-pct"
              className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500"
            >
              Haggle room
            </label>
            <div className="mt-2 flex items-center gap-2">
              <input
                id="haggle-pct"
                type="number"
                min={MIN_HAGGLE_PCT * 100}
                max={MAX_HAGGLE_PCT * 100}
                step={1}
                value={Math.round(hagglePct * 100)}
                onChange={handleHaggleChange}
                disabled={isLoading}
                className="w-20 rounded-md border border-gray-300 p-1.5 text-sm focus:border-indigo-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:focus:border-indigo-400"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">
                % built into the listing price
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              Adjusting this re-runs research with your haggle room preference.
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
              Optimal marketing angle
            </p>
            <p className="mt-1 text-sm text-gray-700 dark:text-gray-300">
              {report.marketing_angle}
            </p>
          </div>

          <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
              Sources
            </p>
            {report.sources?.length ? (
              <ul className="mt-2 flex flex-col gap-1">
                {report.sources.map((source, index) => (
                  <li key={index}>
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-indigo-600 hover:underline dark:text-indigo-400"
                    >
                      {source.title ?? source.url}
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">No sources returned.</p>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onBack}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
            >
              Back to identify
            </button>
            <button
              type="button"
              onClick={() => runResearch()}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
            >
              Redo research
            </button>
            <button
              type="button"
              onClick={() => onApprove(report)}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 dark:bg-indigo-500 dark:hover:bg-indigo-400"
            >
              Approve & continue to listing
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
