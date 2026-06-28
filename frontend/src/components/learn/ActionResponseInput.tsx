interface Props {
  inputType: 'text' | 'action_select'
  options: string[]
  value: string
  onChange: (v: string) => void
  placeholder?: string
  label: string
}

export default function ActionResponseInput({ inputType, options, value, onChange, placeholder, label }: Props) {
  if (inputType === 'action_select' && options.length > 0) {
    return (
      <div>
        <p className="text-sm font-medium text-gray-700 mb-3">{label}</p>
        <div className="grid gap-2">
          {options.map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className={`w-full text-left px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                value === opt
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-gray-200 bg-white text-gray-700 hover:border-primary-300 hover:bg-gray-50'
              }`}
            >
              {opt}
            </button>
          ))}
        </div>
        {value && (
          <p className="mt-2 text-xs text-primary-600 font-medium">
            Selected: {value}
          </p>
        )}
      </div>
    )
  }

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? 'Type your answer…'}
        className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
      />
    </div>
  )
}
