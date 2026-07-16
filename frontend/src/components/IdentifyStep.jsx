import { useEffect, useRef, useState } from 'react'
import { identifyItem } from '../api.js'
import { logger } from '../logger.js'
import useRecentQueries from '../useRecentQueries.js'
import StatusLog, { useStatusLog } from './StatusLog.jsx'

function ImagePreviewList({ images }) {
  if (images.length === 0) return null
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {images.map((image) => (
        <img
          key={image.previewUrl}
          src={image.previewUrl}
          alt={image.file.name}
          className="h-20 w-20 rounded-md border border-gray-200 object-cover dark:border-gray-700"
        />
      ))}
    </div>
  )
}

function RecentQueries({ queries, onSelect, onClear }) {
  if (queries.length === 0) return null
  return (
    <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm font-medium text-gray-700 dark:text-gray-200">
          Recent searches
        </p>
        <button
          type="button"
          onClick={onClear}
          className="text-xs text-gray-500 hover:underline dark:text-gray-400"
        >
          Clear
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {queries.map((query) => (
          <button
            key={query}
            type="button"
            onClick={() => onSelect(query)}
            className="rounded-full border border-gray-200 px-3 py-1 text-sm text-gray-700 transition-colors hover:border-indigo-300 hover:text-indigo-600 dark:border-gray-700 dark:text-gray-300 dark:hover:border-indigo-500 dark:hover:text-indigo-400"
          >
            {query}
          </button>
        ))}
      </div>
    </div>
  )
}

function CandidateCard({ candidate, selected, onSelect }) {
  const title =
    candidate.title ?? candidate.name ?? candidate.label ?? 'Candidate item'
  const subtitle = [candidate.brand, candidate.model]
    .filter(Boolean)
    .join(' · ')
  const description = candidate.description ?? candidate.summary
  const confidence = candidate.confidence ?? candidate.confidence_score

  return (
    <button
      type="button"
      onClick={onSelect}
      className={[
        'w-full rounded-lg border p-4 text-left transition-colors',
        selected
          ? 'border-indigo-500 bg-indigo-50 ring-1 ring-indigo-500 dark:border-indigo-400 dark:bg-indigo-950 dark:ring-indigo-400'
          : 'border-gray-200 bg-white hover:border-indigo-300 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-indigo-500',
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-gray-900 dark:text-gray-50">{title}</p>
          {subtitle && <p className="text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>}
        </div>
        {confidence !== undefined && (
          <span className="whitespace-nowrap rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300">
            {typeof confidence === 'number'
              ? `${Math.round(confidence * 100)}% match`
              : confidence}
          </span>
        )}
      </div>
      {description && (
        <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{description}</p>
      )}
    </button>
  )
}

export default function IdentifyStep({ onLocked }) {
  const [turns, setTurns] = useState([])
  const [description, setDescription] = useState('')
  const [pendingImages, setPendingImages] = useState([])
  const [context, setContext] = useState(undefined)
  const [latestCandidates, setLatestCandidates] = useState([])
  const [latestLocked, setLatestLocked] = useState(false)
  const [selectedCandidateIndex, setSelectedCandidateIndex] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)
  const { lines: statusLines, start: startStatus, finish: finishStatus, fail: failStatus, reset: resetStatus } =
    useStatusLog()
  const { recentQueries, addQuery, clearQueries } = useRecentQueries()

  useEffect(() => {
    return () => {
      for (const image of pendingImages) {
        URL.revokeObjectURL(image.previewUrl)
      }
    }
  }, [pendingImages])

  function handleFilesSelected(event) {
    const files = Array.from(event.target.files ?? [])
    setPendingImages((current) => [
      ...current,
      ...files.map((file) => ({ file, previewUrl: URL.createObjectURL(file) })),
    ])
  }

  function removePendingImage(previewUrl) {
    setPendingImages((current) => {
      const match = current.find((image) => image.previewUrl === previewUrl)
      if (match) URL.revokeObjectURL(match.previewUrl)
      return current.filter((image) => image.previewUrl !== previewUrl)
    })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (!description.trim() && pendingImages.length === 0) {
      setError('Add a description or at least one photo before submitting.')
      return
    }

    setIsSubmitting(true)
    setError(null)
    resetStatus()

    const subject = description.trim() || 'photos'
    const stages = [
      pendingImages.length > 0 ? `Uploading ${pendingImages.length} photo(s)` : null,
      `Identifying ${subject}`,
      'Matching candidates',
    ].filter(Boolean)
    startStatus(stages)

    const userTurn = {
      role: 'user',
      text: description,
      images: pendingImages,
    }

    try {
      const response = await identifyItem({
        description,
        images: pendingImages.map((image) => image.file),
        context,
      })

      const candidates = response.candidates ?? []
      const locked = Boolean(response.locked)
      finishStatus(locked ? 'identified' : 'done')
      logger.info('identify response', { candidates: candidates.length, locked })
      addQuery(description)

      setTurns((current) => [
        ...current,
        userTurn,
        { role: 'assistant', candidates, locked },
      ])
      setLatestCandidates(candidates)
      setLatestLocked(locked)
      setSelectedCandidateIndex(candidates.length === 1 ? 0 : null)
      setContext(response.context ?? context)
      setDescription('')
      setPendingImages([])
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      failStatus('failed')
      logger.error('identify failed', err)
      setError(err.message ?? 'Failed to reach the identification service.')
    } finally {
      setIsSubmitting(false)
    }
  }

  function handleSelectRecentQuery(query) {
    setDescription(query)
  }

  function handleConfirmLock() {
    if (selectedCandidateIndex === null) return
    const item = latestCandidates[selectedCandidateIndex]
    onLocked(item, context)
  }

  const hasCandidates = latestCandidates.length > 0

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-50">
          Identify your item
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Describe the item and upload one or more photos. We&apos;ll ask
          follow-up questions until we&apos;re confident about the exact
          item.
        </p>
      </div>

      {turns.length > 0 && (
        <div className="flex flex-col gap-3 rounded-lg border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900">
          {turns.map((turn, index) =>
            turn.role === 'user' ? (
              <div key={index} className="self-end rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white max-w-[85%] dark:bg-indigo-500">
                {turn.text && <p>{turn.text}</p>}
                <ImagePreviewList images={turn.images} />
              </div>
            ) : (
              <div
                key={index}
                className="self-start max-w-[85%] rounded-lg bg-white px-4 py-3 text-sm shadow-sm dark:bg-gray-800"
              >
                <p className="mb-2 font-medium text-gray-700 dark:text-gray-200">
                  {turn.locked
                    ? 'Item identified with high confidence:'
                    : 'Here is what I found so far — tell me more to narrow it down:'}
                </p>
                <div className="flex flex-col gap-2">
                  {turn.candidates.map((candidate, cIndex) => (
                    <CandidateCard
                      key={cIndex}
                      candidate={candidate}
                      selected={false}
                      onSelect={() => {}}
                    />
                  ))}
                </div>
              </div>
            ),
          )}
        </div>
      )}

      {hasCandidates && (
        <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-700">
          <p className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-200">
            Select the candidate that matches your item:
          </p>
          <div className="flex flex-col gap-2">
            {latestCandidates.map((candidate, index) => (
              <CandidateCard
                key={index}
                candidate={candidate}
                selected={selectedCandidateIndex === index}
                onSelect={() => setSelectedCandidateIndex(index)}
              />
            ))}
          </div>
          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              disabled={selectedCandidateIndex === null}
              onClick={handleConfirmLock}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-gray-300 dark:bg-indigo-500 dark:hover:bg-indigo-400 dark:disabled:bg-gray-700"
            >
              {latestLocked
                ? 'Confirm & continue to research'
                : 'Lock this item anyway & continue'}
            </button>
            {!latestLocked && (
              <span className="text-xs text-amber-600 dark:text-amber-400">
                Not confident yet — add more details below, or confirm manually.
              </span>
            )}
          </div>
        </div>
      )}

      <RecentQueries
        queries={recentQueries}
        onSelect={handleSelectRecentQuery}
        onClear={clearQueries}
      />

      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-3 rounded-lg border border-gray-200 p-4 dark:border-gray-700"
      >
        <label className="text-sm font-medium text-gray-700 dark:text-gray-200" htmlFor="description">
          {hasCandidates ? 'Add more details' : 'Describe the item'}
        </label>
        <textarea
          id="description"
          rows={3}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="e.g. Black leather office chair, adjustable height, minor scuff on one armrest"
          className="w-full rounded-md border border-gray-300 p-2 text-sm focus:border-indigo-500 focus:outline-none dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:placeholder-gray-500 dark:focus:border-indigo-400"
        />

        <label className="text-sm font-medium text-gray-700 dark:text-gray-200" htmlFor="images">
          Photos
        </label>
        <input
          id="images"
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFilesSelected}
          className="text-sm text-gray-700 dark:text-gray-300"
        />
        <ImagePreviewList images={pendingImages} />
        {pendingImages.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {pendingImages.map((image) => (
              <button
                key={image.previewUrl}
                type="button"
                onClick={() => removePendingImage(image.previewUrl)}
                className="text-xs text-red-600 hover:underline dark:text-red-400"
              >
                Remove {image.file.name}
              </button>
            ))}
          </div>
        )}

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        {(isSubmitting || statusLines.length > 0) && (
          <StatusLog lines={statusLines} />
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="mt-1 self-start rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-gray-300 dark:bg-indigo-500 dark:hover:bg-indigo-400 dark:disabled:bg-gray-700"
        >
          {isSubmitting
            ? 'Working...'
            : hasCandidates
              ? 'Resubmit with more details'
              : 'Identify item'}
        </button>
      </form>
    </div>
  )
}
