import { useState } from 'react'
import { fillMarketplaceListing } from '../api.js'
import { logger } from '../logger.js'

/**
 * Derive the price to prefill in the dialog from a research report.
 *
 * Prefers `pricing.listing_price` (the Python-computed haggle-adjusted price)
 * and falls back to the raw `price_range` (low, then high) when pricing is
 * absent or incomplete, or to blank when neither is usable.
 *
 * @param {Record<string, unknown> | null | undefined} research
 * @returns {number | ''}
 */
export function derivePrefillPrice(research) {
  const pricing = research?.pricing
  if (pricing && typeof pricing === 'object' && typeof pricing.listing_price === 'number') {
    return pricing.listing_price
  }
  const range = research?.price_range
  if (range && typeof range === 'object') {
    if (typeof range.low === 'number') return range.low
    if (typeof range.high === 'number') return range.high
  }
  return ''
}

export default function PostToMarketplaceDialog({
  marketplace,
  listing,
  research,
  photos = [],
  onClose,
}) {
  const [phase, setPhase] = useState('readiness')
  const [price, setPrice] = useState(() => derivePrefillPrice(research))
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  async function handleConfirm() {
    setPhase('filling')
    setError(null)
    try {
      const response = await fillMarketplaceListing({
        marketplace,
        listing,
        price: price === '' ? undefined : Number(price),
        images: photos,
      })
      logger.info('posting fill response', response)
      setResult(response)
      setPhase('success')
    } catch (err) {
      logger.error('posting fill failed', err)
      setError(err.message ?? 'Failed to fill the marketplace listing.')
      setPhase('error')
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Post to Facebook Marketplace"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-gray-900">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-50">
          Post to Facebook Marketplace
        </h3>

        {phase === 'readiness' && (
          <div className="mt-4 flex flex-col gap-4">
            <ol className="list-decimal space-y-1 pl-5 text-sm text-gray-600 dark:text-gray-300">
              <li>Open Chrome and log into Facebook.</li>
              <li>
                Enable remote debugging once at{' '}
                <code className="rounded bg-gray-100 px-1 dark:bg-gray-800">
                  chrome://inspect/#remote-debugging
                </code>
                .
              </li>
              <li>Keep Chrome open — this connects to your existing browser session.</li>
            </ol>
            <div>
              <label
                htmlFor="post-price"
                className="text-sm font-medium text-gray-700 dark:text-gray-200"
              >
                Price (optional)
              </label>
              <input
                id="post-price"
                type="number"
                step="0.01"
                value={price}
                onChange={(event) => setPrice(event.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 p-2 text-sm focus:border-indigo-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:focus:border-indigo-400"
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 dark:bg-indigo-500 dark:hover:bg-indigo-400"
              >
                OK, fill the form
              </button>
            </div>
          </div>
        )}

        {phase === 'filling' && (
          <div className="mt-4 flex flex-col gap-3">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              Connecting to Chrome and filling the form. Approve the connection prompt in
              Chrome if it appears — this can take a moment.
            </p>
            <div
              role="status"
              className="text-sm font-medium text-indigo-700 dark:text-indigo-300"
            >
              Working...
            </div>
          </div>
        )}

        {phase === 'success' && (
          <div className="mt-4 flex flex-col gap-3">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              The form has been filled in Chrome. Review the listing there and click Publish
              yourself when you&apos;re ready.
            </p>
            {result?.steps_summary?.length > 0 && (
              <ul className="max-h-40 overflow-y-auto rounded-md bg-gray-50 p-2 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300">
                {result.steps_summary.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ul>
            )}
            <div className="flex justify-end">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 dark:bg-indigo-500 dark:hover:bg-indigo-400"
              >
                Done
              </button>
            </div>
          </div>
        )}

        {phase === 'error' && (
          <div className="mt-4 flex flex-col gap-3">
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-500 dark:bg-indigo-500 dark:hover:bg-indigo-400"
              >
                Retry
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
