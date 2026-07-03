import type { DifficultyLevel } from '@/types'

const config: Record<DifficultyLevel, { label: string; classes: string }> = {
  beginner: { label: 'Beginner', classes: 'bg-clinical-100 text-clinical-700' },
  intermediate: { label: 'Intermediate', classes: 'bg-amber-100 text-amber-700' },
  advanced: { label: 'Advanced', classes: 'bg-red-100 text-red-700' },
}

export default function DifficultyBadge({ level }: { level: DifficultyLevel }) {
  const { label, classes } = config[level] ?? config.intermediate
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${classes}`}>
      {label}
    </span>
  )
}
