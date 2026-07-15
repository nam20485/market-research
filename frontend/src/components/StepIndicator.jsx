const STEPS = [
  { id: 'identify', label: '1. Identify' },
  { id: 'research', label: '2. Research' },
  { id: 'listing', label: '3. Listing' },
]

export default function StepIndicator({ currentStep }) {
  const currentIndex = STEPS.findIndex((step) => step.id === currentStep)

  return (
    <ol className="flex items-center justify-center gap-2 py-6">
      {STEPS.map((step, index) => {
        const isActive = index === currentIndex
        const isComplete = index < currentIndex
        return (
          <li key={step.id} className="flex items-center gap-2">
            <span
              className={[
                'rounded-full px-4 py-1.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-indigo-600 text-white shadow dark:bg-indigo-500'
                  : isComplete
                    ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300'
                    : 'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500',
              ].join(' ')}
            >
              {step.label}
            </span>
            {index < STEPS.length - 1 && (
              <span className="h-px w-8 bg-gray-300 dark:bg-gray-700" aria-hidden="true" />
            )}
          </li>
        )
      })}
    </ol>
  )
}
