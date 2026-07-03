interface Props {
  currentStep: number   // 1-based
  totalSteps: number
  stepTitles: string[]
}

export default function TrainingProgressIndicator({ currentStep, totalSteps, stepTitles }: Props) {
  return (
    <div className="w-full">
      {/* Step dots */}
      <div className="flex items-center gap-1">
        {Array.from({ length: totalSteps }, (_, i) => {
          const step = i + 1
          const done = step < currentStep
          const active = step === currentStep
          return (
            <div key={step} className="flex items-center flex-1 last:flex-none">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 transition-colors ${
                  done
                    ? 'bg-primary-600 text-white'
                    : active
                    ? 'bg-primary-100 text-primary-700 ring-2 ring-primary-500'
                    : 'bg-gray-100 text-gray-400'
                }`}
              >
                {done ? '✓' : step}
              </div>
              {i < totalSteps - 1 && (
                <div className={`flex-1 h-0.5 mx-1 ${done ? 'bg-primary-400' : 'bg-gray-200'}`} />
              )}
            </div>
          )
        })}
      </div>
      {/* Active step title */}
      {stepTitles[currentStep - 1] && (
        <p className="mt-2 text-xs font-medium text-primary-700 text-center">
          Step {currentStep} of {totalSteps}: {stepTitles[currentStep - 1]}
        </p>
      )}
    </div>
  )
}
