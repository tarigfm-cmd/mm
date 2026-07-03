const COLORS: Record<string, string> = {
  UK:  'bg-blue-50 text-blue-700 ring-1 ring-blue-200',
  US:  'bg-red-50 text-red-700 ring-1 ring-red-200',
  GCC: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200',
  AU:  'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
}

interface Props {
  region: string
}

export default function RegionBadge({ region }: Props) {
  const cls = COLORS[region] ?? 'bg-gray-100 text-gray-600 ring-1 ring-gray-200'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold ${cls}`}>
      {region}
    </span>
  )
}
