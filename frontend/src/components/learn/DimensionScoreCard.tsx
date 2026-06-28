import {
  CheckCircleIcon,
  XCircleIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/react/24/outline'
import type { DimensionFeedbackItem } from '@/types/learn'

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

interface Props {
  items: DimensionFeedbackItem[]
}

export default function DimensionScoreCard({ items }: Props) {
  const scored = items.filter((i) => i.status !== 'not_assessable')
  const notAssessable = items.filter((i) => i.status === 'not_assessable')

  return (
    <div className="space-y-3">
      {scored.length > 0 && (
        <div className="space-y-2">
          {scored.map((item) => (
            <div
              key={item.dimension}
              className={`flex items-start gap-3 p-3 rounded-lg border ${
                item.status === 'passed'
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              }`}
            >
              {item.status === 'passed' ? (
                <CheckCircleIcon className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
              ) : (
                <XCircleIcon className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              )}
              <div>
                <p className={`text-xs font-semibold ${item.status === 'passed' ? 'text-green-800' : 'text-red-800'}`}>
                  {DIMENSION_LABELS[item.dimension] ?? item.dimension.replace(/_/g, ' ')}
                </p>
                <p className={`text-xs mt-0.5 ${item.status === 'passed' ? 'text-green-700' : 'text-red-700'}`}>
                  {item.feedback}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {notAssessable.length > 0 && (
        <details className="group">
          <summary className="flex items-center gap-2 cursor-pointer text-xs text-gray-500 select-none">
            <QuestionMarkCircleIcon className="w-4 h-4" />
            {notAssessable.length} dimension{notAssessable.length !== 1 ? 's' : ''} not automatically assessed
          </summary>
          <div className="mt-2 space-y-1.5">
            {notAssessable.map((item) => (
              <div key={item.dimension} className="flex items-start gap-2 px-3 py-2 bg-gray-50 rounded-lg">
                <QuestionMarkCircleIcon className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-medium text-gray-500">
                    {DIMENSION_LABELS[item.dimension] ?? item.dimension.replace(/_/g, ' ')}
                  </p>
                  <p className="text-xs text-gray-400">{item.feedback}</p>
                </div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
