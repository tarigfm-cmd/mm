const CONFIG: Record<string, { label: string; cls: string }> = {
  active:          { label: 'Active',           cls: 'bg-green-50 text-green-700' },
  needs_review:    { label: 'Needs Review',     cls: 'bg-amber-50 text-amber-700' },
  superseded:      { label: 'Superseded',       cls: 'bg-gray-100 text-gray-500' },
  region_specific: { label: 'Region-Specific',  cls: 'bg-blue-50 text-blue-700' },
  retired:         { label: 'Retired',          cls: 'bg-red-50 text-red-600' },
}

interface Props {
  evidenceStatus: string
}

export default function EvidenceStatusBadge({ evidenceStatus }: Props) {
  const cfg = CONFIG[evidenceStatus] ?? { label: evidenceStatus, cls: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
}
