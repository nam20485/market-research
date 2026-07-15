import { useCallback, useEffect, useState } from 'react'
import { requestResearch } from '../api.js'

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

export default function ResearchStep({ item, onApprove, onBack }) {
  const [report, setReport] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const runResearch = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await requestResearch({ item })
      setReport(result)
    } catch (err) {
      setError(err.message ?? 'Failed to generate the market research report.')
    } finally {
      setIsLoading(false)
    }
  }, [item])

  useEffect(() => {
    runResearch()
  }, [runResearch])

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

      {isLoading && (
        <p className="text-sm text-gray-500 dark:text-gray-400">Researching comparable listings...</p>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
          <button
            type="button"
            onClick={runResearch}
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
              onClick={runResearch}
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
