import { InformationCircleIcon } from '@heroicons/react/24/outline'
import type { TrainingFlowStep } from '@/types/learn'

const SAFE_CONTENT_LABELS: Record<string, string> = {
  patient_profile: 'Patient profile',
  presenting_complaint: 'Presenting complaint',
  context: 'Context',
  domain: 'Domain',
  subtopic: 'Subtopic',
  prompt: 'Question',
  station_title: 'Station title',
  candidate_task: 'Candidate task',
  safety_concern: 'Safety concern',
}

interface Props {
  step: TrainingFlowStep
}

export default function TrainingStepCard({ step }: Props) {
  const hasContent = Object.keys(step.safe_content).length > 0

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 p-4 bg-primary-50 border border-primary-200 rounded-xl">
        <InformationCircleIcon className="w-5 h-5 text-primary-600 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-primary-800">{step.instruction}</p>
      </div>

      {hasContent && (
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <dl className="space-y-3">
            {Object.entries(step.safe_content).map(([key, val]) => {
              if (val === null || val === undefined || val === '') return null
              const label = SAFE_CONTENT_LABELS[key] ?? key.replace(/_/g, ' ')
              return (
                <div key={key} className="flex gap-3">
                  <dt className="text-xs font-medium text-gray-500 w-40 flex-shrink-0 capitalize pt-0.5">
                    {label}
                  </dt>
                  <dd className="text-sm text-gray-800 flex-1 whitespace-pre-wrap break-words">
                    {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                  </dd>
                </div>
              )
            })}
          </dl>
        </div>
      )}
    </div>
  )
}
