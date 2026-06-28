const CONFIG: Record<string, { label: string; cls: string }> = {
  draft:               { label: 'Draft',               cls: 'bg-gray-100 text-gray-600' },
  imported:            { label: 'Imported',             cls: 'bg-blue-50 text-blue-700' },
  pending_review:      { label: 'Pending Review',       cls: 'bg-amber-50 text-amber-700' },
  clinically_approved: { label: 'Clinically Approved',  cls: 'bg-emerald-50 text-emerald-700' },
  published:           { label: 'Published',            cls: 'bg-green-100 text-green-800' },
  unpublished:         { label: 'Unpublished',          cls: 'bg-gray-100 text-gray-500' },
  needs_update:        { label: 'Needs Update',         cls: 'bg-orange-50 text-orange-700' },
  retired:             { label: 'Retired',              cls: 'bg-red-50 text-red-600' },
}

interface Props {
  status: string
  size?: 'sm' | 'md'
}

export default function StatusBadge({ status, size = 'sm' }: Props) {
  const cfg = CONFIG[status] ?? { label: status, cls: 'bg-gray-100 text-gray-600' }
  const base = size === 'sm' ? 'text-xs' : 'text-sm'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full font-medium ${base} ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
}
