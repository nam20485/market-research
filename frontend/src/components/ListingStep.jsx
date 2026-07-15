import { useCallback, useEffect, useState } from 'react'
import { generateListing } from '../api.js'

function ListingCard({ marketplace, listing }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    const text = `${listing.title}\n\n${listing.description}`
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
          {marketplace}
        </h3>
        <button
          type="button"
          onClick={handleCopy}
          className="rounded-md border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
        >
          {copied ? 'Copied!' : 'Copy to clipboard'}
        </button>
      </div>
      <p className="font-medium text-gray-900 dark:text-gray-50">{listing.title}</p>
      <p className="whitespace-pre-wrap text-sm text-gray-600 dark:text-gray-300">
        {listing.description}
      </p>
    </div>
  )
}

export default function ListingStep({ item, research, onBack, onStartOver }) {
  const [listing, setListing] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const runGenerate = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const result = await generateListing({ item, research })
      setListing(result)
    } catch (err) {
      setError(err.message ?? 'Failed to generate listing content.')
    } finally {
      setIsLoading(false)
    }
  }, [item, research])

  useEffect(() => {
    runGenerate()
  }, [runGenerate])

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-50">
          Your listing is ready
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Copy-paste-ready titles and descriptions for each marketplace.
        </p>
      </div>

      {isLoading && (
        <p className="text-sm text-gray-500 dark:text-gray-400">Generating listing content...</p>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          {error}
          <button
            type="button"
            onClick={runGenerate}
            className="ml-3 font-medium underline"
          >
            Retry
          </button>
        </div>
      )}

      {!isLoading && listing && (
        <div className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            {listing.facebook && (
              <ListingCard marketplace="Facebook Marketplace" listing={listing.facebook} />
            )}
            {listing.offerup && (
              <ListingCard marketplace="OfferUp" listing={listing.offerup} />
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onBack}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
            >
              Back to research
            </button>
            <button
              type="button"
              onClick={onStartOver}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
            >
              Start over with a new item
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
