const CONFIG: Record<string, { label: string; cls: string }> = {
  case:                   { label: 'Case',              cls: 'bg-violet-50 text-violet-700' },
  simulation:             { label: 'Simulation',        cls: 'bg-cyan-50 text-cyan-700' },
  osce_station:           { label: 'OSCE Station',      cls: 'bg-indigo-50 text-indigo-700' },
  prescription_screening: { label: 'Rx Screening',      cls: 'bg-teal-50 text-teal-700' },
  drill:                  { label: 'Drill',             cls: 'bg-pink-50 text-pink-700' },
  game:                   { label: 'Game',              cls: 'bg-orange-50 text-orange-700' },
  evidence_source:        { label: 'Evidence Source',   cls: 'bg-lime-50 text-lime-700' },
  taxonomy_node:          { label: 'Taxonomy',          cls: 'bg-stone-50 text-stone-700' },
}

interface Props {
  contentType: string
}

export default function ContentTypeBadge({ contentType }: Props) {
  const cfg = CONFIG[contentType] ?? { label: contentType, cls: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
}
