import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ChartBarIcon,
  ClipboardDocumentListIcon,
  BookOpenIcon,
  ExclamationTriangleIcon,
  TrophyIcon,
  ArrowRightIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline'
import { learnApi } from '@/services/learnApi'
import type { LearnerProgressSummary, LearnerSessionSummary } from '@/types/learn'
import LoadingSpinner from '@/components/LoadingSpinner'

const DIMENSION_LABELS: Record<string, string> = {
  red_flag_recognition: 'Red Flag Recognition',
  triage_or_referral_decision: 'Triage / Referral Decision',
  medication_safety: 'Medication Safety',
  counseling_quality: 'Counseling Quality',
  documentation_quality: 'Documentation Quality',
  calculation_accuracy: 'Calculation Accuracy',
  interaction_detection: 'Interaction Detection',
  communication_safety: 'Communication Safety',
}

const TYPE_COLOR: Record<string, string> = {
  case: 'bg-blue-100 text-blue-700',
  simulation: 'bg-purple-100 text-purple-700',
  osce_station: 'bg-teal-100 text-teal-700',
  prescription_screening: 'bg-amber-100 text-amber-700',
  drill: 'bg-green-100 text-green-700',
  game: 'bg-pink-100 text-pink-700',
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  accent = 'text-primary-600',
}: {
  icon: React.ElementType
  label: string
  value: string
  sub?: string
  accent?: string
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 flex items-start gap-4">
      <div className={`p-2.5 rounded-lg bg-gray-50 ${accent}`}>
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

function WeaknessBar({ label, rate }: { label: string; rate: number }) {
  const pct = Math.round(rate * 100)
  const color = pct >= 50 ? 'bg-red-500' : pct >= 25 ? 'bg-amber-400' : 'bg-green-400'
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-xs text-gray-600">{DIMENSION_LABELS[label] ?? label.replace(/_/g, ' ')}</span>
        <span className={`text-xs font-semibold ${pct >= 50 ? 'text-red-600' : pct >= 25 ? 'text-amber-600' : 'text-green-600'}`}>
          {pct}% miss rate
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function SessionRow({ session }: { session: LearnerSessionSummary }) {
  const pct = session.score_percent
  const color = pct === null ? 'text-gray-400' : pct >= 80 ? 'text-green-600' : pct >= 50 ? 'text-amber-600' : 'text-red-600'
  return (
    <div className="flex items-center justify-between px-4 py-3 bg-gray-50 rounded-lg text-sm">
      <div className="flex items-center gap-3 min-w-0">
        {session.content_type && (
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium flex-shrink-0 ${TYPE_COLOR[session.content_type] ?? 'bg-gray-100 text-gray-600'}`}>
            {session.content_type.replace('_', ' ')}
          </span>
        )}
        <span className="text-gray-700 truncate">{session.content_title ?? 'Unknown item'}</span>
        <span className="text-xs text-gray-400 flex-shrink-0">{session.region_code}</span>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 ml-3">
        {session.status === 'completed' && (
          <CheckCircleIcon className="w-4 h-4 text-green-500" />
        )}
        <span className={`font-semibold ${color}`}>
          {pct !== null ? `${pct}%` : '—'}
        </span>
        <span className="text-xs text-gray-400">
          {new Date(session.started_at).toLocaleDateString()}
        </span>
      </div>
    </div>
  )
}

export default function TrainingProgressPage() {
  const [summary, setSummary] = useState<LearnerProgressSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    learnApi.getProgress()
      .then(setSummary)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <LoadingSpinner label="Loading progress…" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 max-w-lg">
        <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
        Failed to load progress. Please try again.
      </div>
    )
  }

  if (!summary) return null

  const hasAttempts = summary.total_attempts > 0 || summary.completed_sessions > 0
  const topWeaknesses = Object.entries(summary.dimension_breakdown)
    .sort(([, a], [, b]) => b - a)
    .filter(([, rate]) => rate > 0)

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Training Progress</h1>
          <p className="text-sm text-gray-500 mt-1">Your performance across published content</p>
        </div>
        <Link
          to="/learn/content"
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
        >
          <BookOpenIcon className="w-4 h-4" />
          Browse library
        </Link>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={ClipboardDocumentListIcon}
          label="Total attempts"
          value={String(summary.total_attempts)}
          accent="text-primary-600"
        />
        <StatCard
          icon={CheckCircleIcon}
          label="Completed sessions"
          value={String(summary.completed_sessions)}
          sub="guided training sessions"
          accent="text-green-600"
        />
        <StatCard
          icon={ChartBarIcon}
          label="Session avg score"
          value={summary.average_score_percent !== null ? `${summary.average_score_percent}%` : '—'}
          sub={summary.average_score_percent !== null ? 'from completed sessions' : 'no sessions yet'}
          accent="text-blue-600"
        />
        <StatCard
          icon={TrophyIcon}
          label="Avg attempt score"
          value={summary.average_score !== null ? `${Math.round(summary.average_score * 100)}%` : '—'}
          sub={summary.average_score !== null ? 'across scored items' : 'no scored items yet'}
          accent="text-amber-600"
        />
      </div>

      {/* Strongest / weakest */}
      {(summary.strongest_dimension || summary.weakest_dimension) && (
        <div className="grid sm:grid-cols-2 gap-4">
          {summary.strongest_dimension && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <p className="text-xs font-semibold text-green-700 mb-1">Strongest area</p>
              <p className="text-sm font-medium text-green-900">
                {DIMENSION_LABELS[summary.strongest_dimension] ?? summary.strongest_dimension.replace(/_/g, ' ')}
              </p>
            </div>
          )}
          {summary.weakest_dimension && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <p className="text-xs font-semibold text-red-700 mb-1">Needs focus</p>
              <p className="text-sm font-medium text-red-900">
                {DIMENSION_LABELS[summary.weakest_dimension] ?? summary.weakest_dimension.replace(/_/g, ' ')}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Next recommendation */}
      {(summary.recommended_next_content_type || summary.recommended_next_domain) && (
        <div className="flex items-start gap-3 p-4 bg-primary-50 border border-primary-200 rounded-xl">
          <ArrowRightIcon className="w-5 h-5 text-primary-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-primary-800">Recommended next</p>
            <p className="text-xs text-primary-600 mt-0.5">
              {[
                summary.recommended_next_content_type
                  ? `Content type: ${summary.recommended_next_content_type.replace('_', ' ')}`
                  : null,
                summary.recommended_next_domain ? `Domain: ${summary.recommended_next_domain}` : null,
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
          <Link
            to={`/learn/content${summary.recommended_next_content_type ? `?content_type=${summary.recommended_next_content_type}` : ''}`}
            className="flex-shrink-0 px-3 py-1.5 text-xs font-semibold text-primary-700 border border-primary-300 rounded-lg hover:bg-primary-100"
          >
            Train now
          </Link>
        </div>
      )}

      {/* Empty state */}
      {!hasAttempts && (
        <div className="flex flex-col items-center justify-center py-16 bg-gray-50 rounded-xl border border-dashed border-gray-300">
          <BookOpenIcon className="w-12 h-12 text-gray-300 mb-3" />
          <p className="text-sm font-medium text-gray-500">No training yet</p>
          <p className="text-xs text-gray-400 mt-1">
            Complete training items to see your progress here.
          </p>
          <Link
            to="/learn/content"
            className="mt-4 px-4 py-2 text-sm font-medium text-primary-600 border border-primary-200 rounded-lg hover:bg-primary-50"
          >
            Browse library
          </Link>
        </div>
      )}

      {/* By content type */}
      {Object.keys(summary.attempts_by_content_type).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Attempts by content type</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(summary.attempts_by_content_type)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <span
                  key={type}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium ${TYPE_COLOR[type] ?? 'bg-gray-100 text-gray-600'}`}
                >
                  {type.replace('_', ' ')}
                  <span className="font-bold">{count}</span>
                </span>
              ))}
          </div>
        </div>
      )}

      {/* Weakness breakdown */}
      {topWeaknesses.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Dimension weakness</h2>
          <p className="text-xs text-gray-400 mb-4">
            Proportion of attempts where each safety dimension was missed.
          </p>
          <div className="space-y-4">
            {topWeaknesses.map(([dim, rate]) => (
              <WeaknessBar key={dim} label={dim} rate={rate} />
            ))}
          </div>
        </div>
      )}

      {/* Recent sessions */}
      {summary.recent_sessions.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Recent training sessions</h2>
          <div className="space-y-2">
            {summary.recent_sessions.map((sess) => (
              <SessionRow key={sess.id} session={sess} />
            ))}
          </div>
        </div>
      )}

      {/* Recent attempts (Phase 1 fallback) */}
      {summary.recent_attempts.length > 0 && summary.recent_sessions.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Recent attempts</h2>
          <div className="space-y-2">
            {summary.recent_attempts.map((attempt) => {
              const pct = attempt.score !== null ? Math.round(attempt.score * 100) : null
              const color = pct === null ? 'text-gray-400' : pct >= 80 ? 'text-green-600' : pct >= 50 ? 'text-amber-600' : 'text-red-600'
              return (
                <div
                  key={attempt.id}
                  className="flex items-center justify-between px-4 py-3 bg-gray-50 rounded-lg text-sm"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {attempt.content_type && (
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium flex-shrink-0 ${TYPE_COLOR[attempt.content_type] ?? 'bg-gray-100 text-gray-600'}`}>
                        {attempt.content_type.replace('_', ' ')}
                      </span>
                    )}
                    <span className="text-gray-700 truncate">{attempt.content_title ?? 'Unknown item'}</span>
                    {attempt.region_code && (
                      <span className="text-xs text-gray-400 flex-shrink-0">{attempt.region_code}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0 ml-3">
                    <span className={`font-semibold ${color}`}>
                      {pct !== null ? `${pct}%` : '—'}
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date(attempt.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
