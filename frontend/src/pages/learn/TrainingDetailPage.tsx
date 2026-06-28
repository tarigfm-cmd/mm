import { useState, useEffect } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import {
  ArrowLeftIcon,
  CheckCircleIcon,
  XCircleIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline'
import { learnApi } from '@/services/learnApi'
import type { LearnableContentDetail, LearnerAttemptResult } from '@/types/learn'

const TYPE_COLOR: Record<string, string> = {
  case: 'bg-blue-100 text-blue-700',
  simulation: 'bg-purple-100 text-purple-700',
  osce_station: 'bg-teal-100 text-teal-700',
  prescription_screening: 'bg-amber-100 text-amber-700',
  drill: 'bg-green-100 text-green-700',
  game: 'bg-pink-100 text-pink-700',
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return null
  const pct = Math.round(score * 100)
  const color = pct >= 80 ? 'bg-green-100 text-green-700' : pct >= 50 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
  return (
    <span className={`text-2xl font-bold px-4 py-2 rounded-xl ${color}`}>{pct}%</span>
  )
}

function PayloadViewer({ payload }: { payload: Record<string, unknown> | null }) {
  if (!payload || Object.keys(payload).length === 0) return null

  const renderValue = (v: unknown): string => {
    if (v === null || v === undefined) return '—'
    if (typeof v === 'object') return JSON.stringify(v, null, 2)
    return String(v)
  }

  // Friendly label mappings
  const LABELS: Record<string, string> = {
    prompt: 'Question / Prompt',
    domain: 'Domain',
    subtopic: 'Subtopic',
    context: 'Context',
    patient_profile: 'Patient profile',
    presenting_complaint: 'Presenting complaint',
    candidate_task: 'Candidate task',
    safety_concern: 'Safety concern',
    station_title: 'Station title',
    evidence_ids: 'Evidence references',
    review_status: 'Review status',
    region_localization: 'Region',
    difficulty_1_5: 'Difficulty',
  }

  return (
    <div className="space-y-3">
      {Object.entries(payload).map(([key, value]) => {
        if (!value && value !== 0) return null
        const label = LABELS[key] ?? key.replace(/_/g, ' ')
        return (
          <div key={key} className="flex gap-3">
            <dt className="text-xs font-medium text-gray-500 w-40 flex-shrink-0 capitalize pt-0.5">
              {label}
            </dt>
            <dd className="text-sm text-gray-800 flex-1 whitespace-pre-wrap break-words">
              {renderValue(value)}
            </dd>
          </div>
        )
      })}
    </div>
  )
}

function AttemptForm({
  item,
  regionCode,
  onResult,
}: {
  item: LearnableContentDetail
  regionCode: string
  onResult: (r: LearnerAttemptResult) => void
}) {
  const [response, setResponse] = useState('')
  const [selectedAction, setSelectedAction] = useState('')
  const [redFlagIdentified, setRedFlagIdentified] = useState<boolean | undefined>(undefined)
  const [counselingSelected, setCounselingSelected] = useState<boolean | undefined>(undefined)
  const [submitting, setSubmitting] = useState(false)
  const [startedAt] = useState(Date.now())

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    const elapsed = Math.round((Date.now() - startedAt) / 1000)
    try {
      const result = await learnApi.submitAttempt(item.id, {
        region_code: regionCode,
        attempt_type: item.content_type,
        learner_response: response || undefined,
        selected_action: selectedAction || undefined,
        time_to_decision_seconds: elapsed,
        red_flag_identified: redFlagIdentified,
        counseling_point_selected: counselingSelected,
      })
      onResult(result)
    } catch {
      toast.error('Failed to submit attempt. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const isDrill = item.content_type === 'drill'
  const isCase = item.content_type === 'case' || item.content_type === 'simulation'
  const isRx = item.content_type === 'prescription_screening'

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Free-text response for drills */}
      {isDrill && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Your answer</label>
          <input
            type="text"
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            placeholder="Type your answer…"
            className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
      )}

      {/* Decision / action field for cases and prescriptions */}
      {(isCase || isRx) && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {isRx ? 'Pharmacist action' : 'Clinical decision'}
          </label>
          <input
            type="text"
            value={selectedAction}
            onChange={(e) => setSelectedAction(e.target.value)}
            placeholder={isRx ? 'e.g. Refer, Dispense, Withhold…' : 'e.g. Refer, Treat, Advise…'}
            className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
      )}

      {/* Dimension flags */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-gray-700">Safety assessment</p>
        <div className="flex flex-wrap gap-3">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={redFlagIdentified === true}
              onChange={(e) => setRedFlagIdentified(e.target.checked ? true : false)}
              className="w-4 h-4 rounded text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-700">Red flag identified</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={counselingSelected === true}
              onChange={(e) => setCounselingSelected(e.target.checked ? true : false)}
              className="w-4 h-4 rounded text-primary-600 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-700">Counseling point addressed</span>
          </label>
        </div>
      </div>

      {/* Notes about non-automated scoring */}
      {!isDrill && !isRx && (
        <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
          <InformationCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <span>
            Detailed automated scoring is not available for this content type.
            Your attempt will be recorded and can be reviewed by your supervisor.
          </span>
        </div>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="w-full py-3 text-sm font-semibold text-white bg-primary-600 rounded-xl hover:bg-primary-700 disabled:opacity-40 transition-colors"
      >
        {submitting ? 'Submitting…' : 'Submit attempt'}
      </button>
    </form>
  )
}

function ResultPanel({ result }: { result: LearnerAttemptResult }) {
  const passed = result.score !== null && result.score >= 0.8

  return (
    <div className="space-y-4">
      <div className={`flex items-center gap-4 p-5 rounded-xl border ${
        passed ? 'bg-green-50 border-green-200' : result.score === null ? 'bg-gray-50 border-gray-200' : 'bg-red-50 border-red-200'
      }`}>
        {passed ? (
          <CheckCircleIcon className="w-8 h-8 text-green-500 flex-shrink-0" />
        ) : result.score === null ? (
          <InformationCircleIcon className="w-8 h-8 text-gray-400 flex-shrink-0" />
        ) : (
          <XCircleIcon className="w-8 h-8 text-red-500 flex-shrink-0" />
        )}
        <div className="flex-1">
          <p className={`text-sm font-semibold ${
            passed ? 'text-green-800' : result.score === null ? 'text-gray-700' : 'text-red-800'
          }`}>
            {result.feedback}
          </p>
          {result.score !== null && (
            <p className="text-xs text-gray-500 mt-1">
              Score: {Math.round(result.score * 100)}%
            </p>
          )}
        </div>
        <ScoreBadge score={result.score} />
      </div>

      {result.failed_dimensions.length > 0 && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <p className="text-xs font-semibold text-amber-800 mb-2">Areas to review</p>
          <div className="flex flex-wrap gap-1.5">
            {result.failed_dimensions.map((dim) => (
              <span
                key={dim}
                className="text-xs px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full font-medium"
              >
                {dim.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-start gap-2 p-3 bg-primary-50 border border-primary-200 rounded-lg text-sm text-primary-700">
        <span className="font-medium">Next step:</span> {result.recommended_next_step}
      </div>
    </div>
  )
}

export default function TrainingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const regionCode = searchParams.get('region') ?? 'UK'

  const [item, setItem] = useState<LearnableContentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<LearnerAttemptResult | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    learnApi
      .getDetail(id, regionCode)
      .then(setItem)
      .catch(() => setError('Content not found or not published for this region.'))
      .finally(() => setLoading(false))
  }, [id, regionCode])

  if (loading) {
    return (
      <div className="max-w-2xl space-y-4 animate-pulse">
        <div className="h-6 w-48 bg-gray-100 rounded" />
        <div className="h-4 w-full bg-gray-100 rounded" />
        <div className="h-48 bg-gray-100 rounded-xl" />
      </div>
    )
  }

  if (error || !item) {
    return (
      <div className="max-w-2xl">
        <Link to="/learn/content" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-4">
          <ArrowLeftIcon className="w-4 h-4" /> Back to library
        </Link>
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0" />
          {error ?? 'Content not available.'}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-6">
      <Link to="/learn/content" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeftIcon className="w-4 h-4" /> Training Library
      </Link>

      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${TYPE_COLOR[item.content_type] ?? 'bg-gray-100 text-gray-600'}`}>
            {item.content_type.replace('_', ' ')}
          </span>
          {item.difficulty && (
            <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-gray-100 text-gray-600">
              Level {item.difficulty}
            </span>
          )}
          <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-primary-50 text-primary-600">
            {regionCode}
          </span>
          <span className="text-xs text-gray-400 ml-auto">v{item.version_number}</span>
        </div>

        <h1 className="text-xl font-bold text-gray-900">{item.title}</h1>

        {(item.domain || item.specialty) && (
          <p className="text-sm text-gray-500">
            {[item.domain, item.specialty].filter(Boolean).join(' · ')}
          </p>
        )}

        {item.requires_local_disclaimer && (
          <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
            <ExclamationTriangleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
            This content includes region-specific guidelines. Refer to local protocols.
          </div>
        )}
        {item.requires_protocol_note && (
          <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
            <InformationCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
            Protocol note required. Consult your regional formulary.
          </div>
        )}
      </div>

      {/* Content payload */}
      {item.safe_payload && Object.keys(item.safe_payload).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Content</h2>
          <dl className="space-y-3">
            <PayloadViewer payload={item.safe_payload} />
          </dl>
        </div>
      )}

      {item.localization_notes && (
        <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl text-sm text-gray-600">
          <p className="text-xs font-semibold text-gray-500 mb-1">Localization notes</p>
          {item.localization_notes}
        </div>
      )}

      {/* Attempt form or result */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        {result ? (
          <>
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Your result</h2>
            <ResultPanel result={result} />
            <div className="mt-4 pt-4 border-t border-gray-100 flex gap-3">
              <Link
                to="/learn/content"
                className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Back to library
              </Link>
              <Link
                to="/learn/progress"
                className="px-4 py-2 text-sm font-medium text-primary-700 border border-primary-200 rounded-lg hover:bg-primary-50"
              >
                View my progress
              </Link>
            </div>
          </>
        ) : (
          <>
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Your attempt</h2>
            <AttemptForm item={item} regionCode={regionCode} onResult={setResult} />
          </>
        )}
      </div>
    </div>
  )
}
