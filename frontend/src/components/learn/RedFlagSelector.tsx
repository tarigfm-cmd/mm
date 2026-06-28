import { useState } from 'react'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'

interface Props {
  value: string[]
  onChange: (v: string[]) => void
  /** Free-text entry for unlisted red flags */
  allowFreeText?: boolean
}

export default function RedFlagSelector({ value, onChange, allowFreeText = true }: Props) {
  const [custom, setCustom] = useState('')

  const toggle = (flag: string) => {
    if (value.includes(flag)) {
      onChange(value.filter((f) => f !== flag))
    } else {
      onChange([...value, flag])
    }
  }

  const addCustom = () => {
    const trimmed = custom.trim()
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed])
      setCustom('')
    }
  }

  return (
    <div className="space-y-3">
      {value.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {value.map((flag) => (
            <span
              key={flag}
              className="flex items-center gap-1.5 px-2.5 py-1 bg-red-50 border border-red-200 rounded-full text-xs font-medium text-red-700"
            >
              <ExclamationTriangleIcon className="w-3 h-3" />
              {flag}
              <button
                type="button"
                onClick={() => toggle(flag)}
                className="ml-0.5 hover:text-red-900"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {allowFreeText && (
        <div className="flex gap-2">
          <input
            type="text"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustom() } }}
            placeholder="Type a red flag and press Enter…"
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
          />
          <button
            type="button"
            onClick={addCustom}
            className="px-3 py-2 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs font-medium hover:bg-red-100"
          >
            Add
          </button>
        </div>
      )}

      {value.length === 0 && (
        <p className="text-xs text-gray-400">
          No red flags identified yet — add any alarm symptoms above.
        </p>
      )}
    </div>
  )
}
