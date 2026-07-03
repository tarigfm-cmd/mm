const LABELS = ['Very unsure', 'Unsure', 'Neutral', 'Confident', 'Very confident']

interface Props {
  value: number | undefined
  onChange: (v: number) => void
}

export default function ConfidenceSelector({ value, onChange }: Props) {
  return (
    <div>
      <p className="text-xs font-medium text-gray-500 mb-2">Confidence</p>
      <div className="flex gap-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            title={LABELS[n - 1]}
            className={`w-8 h-8 rounded-full text-xs font-semibold border transition-colors ${
              value === n
                ? 'bg-primary-600 text-white border-primary-600'
                : 'bg-white text-gray-500 border-gray-300 hover:border-primary-400'
            }`}
          >
            {n}
          </button>
        ))}
      </div>
      {value && (
        <p className="text-xs text-gray-400 mt-1">{LABELS[value - 1]}</p>
      )}
    </div>
  )
}
