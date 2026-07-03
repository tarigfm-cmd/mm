import type { ReactNode } from 'react'

interface Props {
  title: string
  value: string | number
  subtitle?: string
  icon?: ReactNode
  accent?: 'blue' | 'green' | 'amber' | 'red' | 'gray'
  loading?: boolean
}

const ACCENT_MAP = {
  blue:  'bg-blue-50 text-blue-600',
  green: 'bg-green-50 text-green-600',
  amber: 'bg-amber-50 text-amber-600',
  red:   'bg-red-50 text-red-600',
  gray:  'bg-gray-100 text-gray-600',
}

export default function StatCard({ title, value, subtitle, icon, accent = 'gray', loading }: Props) {
  const iconCls = ACCENT_MAP[accent]

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-start gap-4">
      {icon && (
        <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center ${iconCls}`}>
          {icon}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{title}</p>
        {loading ? (
          <div className="mt-1 h-7 w-16 bg-gray-100 animate-pulse rounded" />
        ) : (
          <p className="mt-0.5 text-2xl font-bold text-gray-900">{value}</p>
        )}
        {subtitle && <p className="mt-0.5 text-xs text-gray-400">{subtitle}</p>}
      </div>
    </div>
  )
}
