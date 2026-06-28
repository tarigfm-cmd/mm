import { useRef, useEffect, type ReactNode } from 'react'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'

interface Props {
  open: boolean
  title: string
  description: ReactNode
  confirmLabel?: string
  confirmVariant?: 'danger' | 'warning' | 'primary'
  loading?: boolean
  onConfirm: () => void
  onCancel: () => void
}

const VARIANT_MAP = {
  danger:  'bg-red-600 hover:bg-red-700 focus:ring-red-500',
  warning: 'bg-amber-500 hover:bg-amber-600 focus:ring-amber-400',
  primary: 'bg-primary-600 hover:bg-primary-700 focus:ring-primary-500',
}

export default function ConfirmActionDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  confirmVariant = 'danger',
  loading = false,
  onConfirm,
  onCancel,
}: Props) {
  const cancelRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (open) cancelRef.current?.focus()
  }, [open])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Panel */}
      <div className="relative z-10 bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 p-6">
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0 w-10 h-10 rounded-full bg-amber-50 flex items-center justify-center">
            <ExclamationTriangleIcon className="w-5 h-5 text-amber-500" />
          </div>
          <div className="flex-1">
            <h3 id="dialog-title" className="text-base font-semibold text-gray-900">
              {title}
            </h3>
            <div className="mt-2 text-sm text-gray-600">{description}</div>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            ref={cancelRef}
            onClick={onCancel}
            disabled={loading}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className={`px-4 py-2 text-sm font-medium text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 ${VARIANT_MAP[confirmVariant]}`}
          >
            {loading ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
