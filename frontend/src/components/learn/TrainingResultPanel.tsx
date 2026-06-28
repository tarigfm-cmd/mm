import { Link } from 'react-router-dom'
import {
  CheckCircleIcon,
  XCircleIcon,
  InformationCircleIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline'
import type { SessionSubmitResponse } from '@/types/learn'
import DimensionScoreCard from '@/components/learn/DimensionScoreCard'

interface Props {
  result: SessionSubmitResponse
  contentId: string
}

function ScoreBanner({ result }: { result: SessionSubmitResponse }) {
  const pct = result.score_percent
  const isNull = pct === null
  const passed = pct !== null && pct >= 80
  const partial = pct !== null && pct >= 50 && pct < 80

  const bg = isNull
    ? 'bg-gray-50 border-gray-200'
    : passed
    ? 'bg-green-50 border-green-200'
    : partial
    ? 'bg-amber-50 border-amber-200'
    : 'bg-red-50 border-red-200'

  const Icon = isNull
    ? InformationCircleIcon
    : passed
    ? CheckCircleIcon
    : XCircleIcon

  const iconColor = isNull ? 'text-gray-400' : passed ? 'text-green-500' : partial ? 'text-amber-500' : 'text-red-500'

  const label = isNull
    ? 'Training recorded'
    : passed
    ? 'Excellent work!'
    : partial
    ? 'Good attempt'
    : 'Needs improvement'

  return (
    <div className={`flex items-center gap-4 p-5 rounded-xl border ${bg}`}>
      <Icon className={`w-9 h-9 flex-shrink-0 ${iconColor}`} />
      <div className="flex-1">
        <p className="font-semibold text-gray-900">{label}</p>
        {pct !== null ? (
          <p className="text-sm text-gray-600 mt-0.5">Score: {pct}%</p>
        ) : (
          <p className="text-sm text-gray-500 mt-0.5">
            Guided training available — automated scoring limited for this content type.
          </p>
        )}
      </div>
      {pct !== null && (
        <span
          className={`text-2xl font-bold px-4 py-2 rounded-xl ${
            passed
              ? 'bg-green-100 text-green-700'
              : partial
              ? 'bg-amber-100 text-amber-700'
              : 'bg-red-100 text-red-700'
          }`}
        >
          {pct}%
        </span>
      )}
    </div>
  )
}

export default function TrainingResultPanel({ result, contentId: _contentId }: Props) {
  const hasReveal = Object.keys(result.reveal_summary).length > 0

  return (
    <div className="space-y-5">
      <ScoreBanner result={result} />

      {/* Dimension feedback */}
      {result.dimension_feedback.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Dimension feedback</h3>
          <DimensionScoreCard items={result.dimension_feedback} />
        </div>
      )}

      {/* Reveal summary (post-submission hidden fields) */}
      {hasReveal && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-blue-800 mb-3">Expert answer reveal</h3>
          <dl className="space-y-3">
            {Object.entries(result.reveal_summary).map(([label, val]) => (
              <div key={label} className="flex gap-3">
                <dt className="text-xs font-medium text-blue-600 w-40 flex-shrink-0 pt-0.5">
                  {label}
                </dt>
                <dd className="text-sm text-blue-900 flex-1 whitespace-pre-wrap">
                  {val === null || val === undefined
                    ? '—'
                    : typeof val === 'object'
                    ? JSON.stringify(val)
                    : String(val)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {/* Next recommendation */}
      <div className="flex items-start gap-2 p-4 bg-primary-50 border border-primary-200 rounded-xl">
        <ArrowRightIcon className="w-4 h-4 text-primary-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-semibold text-primary-700 mb-0.5">Next step</p>
          <p className="text-sm text-primary-800">{result.next_recommendation}</p>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex gap-3 pt-2">
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
    </div>
  )
}
