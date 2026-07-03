import { useEffect, useState } from 'react'
import {
  ChartBarIcon,
  TrophyIcon,
  ClipboardDocumentListIcon,
  StarIcon,
} from '@heroicons/react/24/outline'
import { progressApi } from '@/services/api'
import type { ProgressSummary } from '@/types'
import LoadingSpinner from '@/components/LoadingSpinner'

const DIFFICULTY_COLORS: Record<string, string> = {
  beginner: 'bg-green-100 text-green-700',
  intermediate: 'bg-amber-100 text-amber-700',
  advanced: 'bg-red-100 text-red-700',
}

const DAYS_OPTIONS = [7, 14, 30, 90]

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color = 'text-primary-600',
}: {
  icon: React.ElementType
  label: string
  value: string
  sub?: string
  color?: string
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-start gap-4">
      <div className={`p-2.5 rounded-lg bg-gray-50 ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xs text-gray-400 font-medium">{label}</p>
        <p className="text-2xl font-bold text-gray-900 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color =
    pct >= 80 ? 'bg-green-100 text-green-700' : pct >= 50 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>{pct}%</span>
  )
}

function TrendChart({ trend }: { trend: ProgressSummary['score_trend'] }) {
  if (trend.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-sm text-gray-400">
        No scored attempts yet
      </div>
    )
  }

  const max = Math.max(...trend.map((p) => p.avg_score))
  const min = Math.min(...trend.map((p) => p.avg_score))
  const range = max - min || 1

  return (
    <div className="flex items-end gap-1.5 h-24 pt-2">
      {trend.map((point, i) => {
        const heightPct = 20 + ((point.avg_score - min) / range) * 80
        const pct = Math.round(point.avg_score * 100)
        return (
          <div key={i} className="flex-1 flex flex-col items-center gap-1 group">
            <div
              className="w-full bg-primary-500 rounded-t-sm opacity-80 group-hover:opacity-100 transition-opacity relative"
              style={{ height: `${heightPct}%` }}
              title={`${point.date}: ${pct}% (${point.count} attempt${point.count !== 1 ? 's' : ''})`}
            />
          </div>
        )
      })}
    </div>
  )
}

export default function ProgressPage() {
  const [summary, setSummary] = useState<ProgressSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    load()
  }, [days])

  const load = async () => {
    setLoading(true)
    try {
      const data = await progressApi.get(days)
      setSummary(data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Progress</h1>
          <p className="mt-1 text-sm text-gray-500">Track your learning across clinical scenarios</p>
        </div>
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
          {DAYS_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                days === d ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48">
          <LoadingSpinner label="Loading progress…" />
        </div>
      ) : summary === null ? null : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard
              icon={ClipboardDocumentListIcon}
              label="Total attempts"
              value={String(summary.total_attempts)}
              sub={`Last ${days} days`}
              color="text-primary-600"
            />
            <StatCard
              icon={ChartBarIcon}
              label="Average score"
              value={summary.avg_score !== null ? `${Math.round(summary.avg_score * 100)}%` : '—'}
              color="text-blue-600"
            />
            <StatCard
              icon={TrophyIcon}
              label="Best score"
              value={summary.best_score !== null ? `${Math.round(summary.best_score * 100)}%` : '—'}
              color="text-amber-500"
            />
          </div>

          {/* Score trend */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-4">Score trend</h2>
            <TrendChart trend={summary.score_trend} />
            {summary.score_trend.length > 0 && (
              <div className="flex justify-between mt-2">
                <span className="text-xs text-gray-400">{summary.score_trend[0].date}</span>
                <span className="text-xs text-gray-400">
                  {summary.score_trend[summary.score_trend.length - 1].date}
                </span>
              </div>
            )}
          </div>

          {/* By difficulty + by specialty */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-sm font-semibold text-gray-900 mb-4">By difficulty</h2>
              {summary.by_difficulty.length === 0 ? (
                <p className="text-sm text-gray-400">No data yet</p>
              ) : (
                <ul className="space-y-3">
                  {summary.by_difficulty.map((item) => (
                    <li key={item.label} className="flex items-center justify-between">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${
                          DIFFICULTY_COLORS[item.label] ?? 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {item.label}
                      </span>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-400">{item.count} attempt{item.count !== 1 ? 's' : ''}</span>
                        <ScoreBadge score={item.avg_score} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-sm font-semibold text-gray-900 mb-4">By specialty</h2>
              {summary.by_specialty.length === 0 ? (
                <p className="text-sm text-gray-400">No specialty data yet</p>
              ) : (
                <ul className="space-y-3">
                  {summary.by_specialty.map((item) => (
                    <li key={item.label} className="flex items-center justify-between">
                      <span className="text-sm text-gray-700 truncate max-w-[140px]">{item.label}</span>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-gray-400">{item.count} attempt{item.count !== 1 ? 's' : ''}</span>
                        <ScoreBadge score={item.avg_score} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {summary.total_attempts === 0 && (
            <div className="text-center py-12 bg-gray-50 rounded-xl border border-dashed border-gray-300">
              <StarIcon className="mx-auto h-10 w-10 text-gray-300 mb-3" />
              <p className="text-sm font-medium text-gray-500">No attempts yet in this period</p>
              <p className="text-xs text-gray-400 mt-1">
                Complete clinical scenarios to see your progress here
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
