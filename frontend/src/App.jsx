import { useState } from 'react'
import StepIndicator from './components/StepIndicator.jsx'
import IdentifyStep from './components/IdentifyStep.jsx'
import ResearchStep from './components/ResearchStep.jsx'
import ListingStep from './components/ListingStep.jsx'
import useTheme from './useTheme.js'

const STEP = {
  IDENTIFY: 'identify',
  RESEARCH: 'research',
  LISTING: 'listing',
}

function ThemeToggle({ theme, onToggle }) {
  const isDark = theme === 'dark'
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className="inline-flex items-center gap-2 rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
    >
      {isDark ? (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="h-4 w-4"
          aria-hidden="true"
        >
          <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4.22 2.05a1 1 0 011.42 1.41l-.71.71a1 1 0 11-1.41-1.41l.7-.71zM17 9a1 1 0 110 2h-1a1 1 0 110-2h1zM4 9a1 1 0 110 2H3a1 1 0 110-2h1zm10.36 5.65a1 1 0 011.41 1.41l-.7.71a1 1 0 01-1.42-1.41l.71-.71zm-9.9 1.41a1 1 0 001.41-1.41l-.7-.71a1 1 0 00-1.42 1.41l.71.71zM5.64 4.05a1 1 0 00-1.41 1.41l.7.71A1 1 0 006.36 4.76l-.71-.71zM10 5a5 5 0 100 10 5 5 0 000-10z" />
        </svg>
      ) : (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="h-4 w-4"
          aria-hidden="true"
        >
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
        </svg>
      )}
      <span>{isDark ? 'Light mode' : 'Dark mode'}</span>
    </button>
  )
}

export default function App() {
  const { theme, toggleTheme } = useTheme()
  const [step, setStep] = useState(STEP.IDENTIFY)
  const [lockedItem, setLockedItem] = useState(null)
  const [research, setResearch] = useState(null)
  const [photos, setPhotos] = useState([])

  function handleItemLocked(item, _context, lockedPhotos) {
    setLockedItem(item)
    setPhotos(lockedPhotos ?? [])
    setStep(STEP.RESEARCH)
  }

  function handleResearchApproved(researchReport) {
    setResearch(researchReport)
    setStep(STEP.LISTING)
  }

  function handleStartOver() {
    setLockedItem(null)
    setResearch(null)
    setPhotos([])
    setStep(STEP.IDENTIFY)
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <header className="border-b border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900">
        <div className="mx-auto flex max-w-5xl items-start justify-between gap-4 px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-50">
              Market Research Assistant
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Identify an item, research the market, and generate ready-to-post
              listings.
            </p>
          </div>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
      </header>

      <StepIndicator currentStep={step} />

      <main className="px-6 pb-16">
        {step === STEP.IDENTIFY && <IdentifyStep onLocked={handleItemLocked} />}
        {step === STEP.RESEARCH && lockedItem && (
          <ResearchStep
            item={lockedItem}
            onApprove={handleResearchApproved}
            onBack={() => setStep(STEP.IDENTIFY)}
          />
        )}
        {step === STEP.LISTING && lockedItem && research && (
          <ListingStep
            item={lockedItem}
            research={research}
            photos={photos}
            onBack={() => setStep(STEP.RESEARCH)}
            onStartOver={handleStartOver}
          />
        )}
      </main>
    </div>
  )
}
