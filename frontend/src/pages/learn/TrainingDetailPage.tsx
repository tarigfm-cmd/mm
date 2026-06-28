import { useState, useEffect, useRef } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import {
  ArrowLeftIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  PlayIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline'
import { learnApi } from '@/services/learnApi'
import type {
  LearnableContentDetail,
  SessionStartResponse,
  SessionSubmitRequest,
  SessionSubmitResponse,
  TrainingFlowResponse,
  TrainingFlowStep,
} from '@/types/learn'
import TrainingProgressIndicator from '@/components/learn/TrainingProgressIndicator'
import TrainingStepCard from '@/components/learn/TrainingStepCard'
import ActionResponseInput from '@/components/learn/ActionResponseInput'
import RedFlagSelector from '@/components/learn/RedFlagSelector'
import ConfidenceSelector from '@/components/learn/ConfidenceSelector'
import TrainingResultPanel from '@/components/learn/TrainingResultPanel'

const TYPE_COLOR: Record<string, string> = {
  case: 'bg-blue-100 text-blue-700',
  simulation: 'bg-purple-100 text-purple-700',
  osce_station: 'bg-teal-100 text-teal-700',
  prescription_screening: 'bg-amber-100 text-amber-700',
  drill: 'bg-green-100 text-green-700',
  game: 'bg-pink-100 text-pink-700',
}

// ---------------------------------------------------------------------------
// Step input capture per step_type
// ---------------------------------------------------------------------------

interface StepResponses {
  redFlags: string[]
  actionSelected: string
  counselingPoints: string[]
  documentationPoints: string[]
  answerText: string
  confidence: number | undefined
}

function StepInputs({
  step,
  responses,
  onChange,
}: {
  step: TrainingFlowStep
  responses: StepResponses
  onChange: (patch: Partial<StepResponses>) => void
}) {
  if (step.input_type === 'none') return null

  if (step.step_type === 'red_flag_check') {
    return (
      <div className="space-y-3">
        <label className="block text-sm font-medium text-gray-700">
          Red flags / alarm symptoms identified
        </label>
        <RedFlagSelector
          value={responses.redFlags}
          onChange={(v) => onChange({ redFlags: v })}
        />
      </div>
    )
  }

  if (step.input_type === 'action_select') {
    return (
      <ActionResponseInput
        inputType="action_select"
        options={step.options}
        value={responses.actionSelected}
        onChange={(v) => onChange({ actionSelected: v })}
        label={step.title}
      />
    )
  }

  if (step.input_type === 'checkbox_list') {
    const items = step.step_type === 'counseling' ? responses.counselingPoints : responses.documentationPoints
    const setItems = step.step_type === 'counseling'
      ? (v: string[]) => onChange({ counselingPoints: v })
      : (v: string[]) => onChange({ documentationPoints: v })

    return (
      <div>
        <p className="text-sm font-medium text-gray-700 mb-3">Select all that apply</p>
        <div className="space-y-2">
          {step.options.map((opt) => {
            const checked = items.includes(opt)
            return (
              <label key={opt} className="flex items-center gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) =>
                    setItems(
                      e.target.checked ? [...items, opt] : items.filter((i) => i !== opt),
                    )
                  }
                  className="w-4 h-4 rounded text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700">{opt}</span>
              </label>
            )
          })}
        </div>
      </div>
    )
  }

  // text input (drill answer, simulation response, red flag free text)
  return (
    <ActionResponseInput
      inputType="text"
      options={[]}
      value={responses.answerText}
      onChange={(v) => onChange({ answerText: v })}
      label={step.title}
      placeholder="Type your answer…"
    />
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function TrainingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const regionCode = searchParams.get('region') ?? 'UK'

  const [item, setItem] = useState<LearnableContentDetail | null>(null)
  const [flow, setFlow] = useState<TrainingFlowResponse | null>(null)
  const [session, setSession] = useState<SessionStartResponse | null>(null)
  const [currentStepIdx, setCurrentStepIdx] = useState(0)
  const [responses, setResponses] = useState<StepResponses>({
    redFlags: [],
    actionSelected: '',
    counselingPoints: [],
    documentationPoints: [],
    answerText: '',
    confidence: undefined,
  })
  const [result, setResult] = useState<SessionSubmitResponse | null>(null)
  const [pageLoading, setPageLoading] = useState(true)
  const [starting, setStarting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const startedAt = useRef(Date.now())

  useEffect(() => {
    if (!id) return
    setPageLoading(true)
    Promise.all([
      learnApi.getDetail(id, regionCode),
      learnApi.getTrainingFlow(id, regionCode),
    ])
      .then(([detail, flowData]) => {
        setItem(detail)
        setFlow(flowData)
      })
      .catch(() => setError('Content not found or not published for this region.'))
      .finally(() => setPageLoading(false))
  }, [id, regionCode])

  const handleStart = async () => {
    if (!id) return
    setStarting(true)
    startedAt.current = Date.now()
    try {
      const sess = await learnApi.startSession(id, regionCode)
      setSession(sess)
      setCurrentStepIdx(0)
    } catch {
      toast.error('Failed to start training session. Please try again.')
    } finally {
      setStarting(false)
    }
  }

  const handleNext = () => {
    if (!flow) return
    if (currentStepIdx < flow.steps.length - 1) {
      setCurrentStepIdx((i) => i + 1)
    }
  }

  const handleSubmit = async () => {
    if (!session) return
    setSubmitting(true)
    const elapsed = Math.round((Date.now() - startedAt.current) / 1000)
    const body: SessionSubmitRequest = {
      action_selected: responses.actionSelected || undefined,
      answer_text: responses.answerText || undefined,
      red_flags_selected: responses.redFlags.length > 0 ? responses.redFlags : undefined,
      counseling_points: responses.counselingPoints.length > 0 ? responses.counselingPoints : undefined,
      documentation_points: responses.documentationPoints.length > 0 ? responses.documentationPoints : undefined,
      confidence: responses.confidence,
      time_to_decision_seconds: elapsed,
    }
    try {
      const res = await learnApi.submitSession(session.session_id, body)
      setResult(res)
    } catch {
      toast.error('Failed to submit training. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (pageLoading) {
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

  const currentStep: TrainingFlowStep | undefined = flow?.steps[currentStepIdx]
  const isLastStep = flow ? currentStepIdx === flow.steps.length - 1 : false
  const stepTitles = flow?.steps.map((s) => s.title) ?? []

  return (
    <div className="max-w-2xl space-y-6">
      <Link to="/learn/content" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeftIcon className="w-4 h-4" /> Training Library
      </Link>

      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${TYPE_COLOR[item.content_type] ?? 'bg-gray-100 text-gray-600'}`}>
            {item.content_type.replace(/_/g, ' ')}
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
          <p className="text-sm text-gray-500">{[item.domain, item.specialty].filter(Boolean).join(' · ')}</p>
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

      {/* Result panel (after submission) */}
      {result && id && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-5">Your result</h2>
          <TrainingResultPanel result={result} contentId={id} />
        </div>
      )}

      {/* Pre-session: start training */}
      {!session && !result && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
          {flow && (
            <div>
              <h2 className="text-sm font-semibold text-gray-700 mb-1">Guided Training</h2>
              <p className="text-xs text-gray-500">
                {flow.total_steps}-step interactive session · {flow.scoring_note}
              </p>
            </div>
          )}
          {item.localization_notes && (
            <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-600">
              <p className="text-xs font-semibold text-gray-500 mb-1">Localization notes</p>
              {item.localization_notes}
            </div>
          )}
          <button
            onClick={handleStart}
            disabled={starting}
            className="w-full flex items-center justify-center gap-2 py-3 text-sm font-semibold text-white bg-primary-600 rounded-xl hover:bg-primary-700 disabled:opacity-40 transition-colors"
          >
            <PlayIcon className="w-4 h-4" />
            {starting ? 'Starting…' : 'Start guided training'}
          </button>
        </div>
      )}

      {/* Active session: step-by-step flow */}
      {session && !result && flow && currentStep && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-6">
          {/* Progress indicator */}
          <TrainingProgressIndicator
            currentStep={currentStepIdx + 1}
            totalSteps={flow.total_steps}
            stepTitles={stepTitles}
          />

          {/* Step content */}
          <div>
            <h2 className="text-base font-semibold text-gray-900 mb-4">{currentStep.title}</h2>
            <TrainingStepCard step={currentStep} />
          </div>

          {/* Step input */}
          {currentStep.input_required && (
            <div className="pt-2">
              <StepInputs
                step={currentStep}
                responses={responses}
                onChange={(patch) => setResponses((prev) => ({ ...prev, ...patch }))}
              />
            </div>
          )}

          {/* Confidence on last step */}
          {isLastStep && (
            <ConfidenceSelector
              value={responses.confidence}
              onChange={(v) => setResponses((prev) => ({ ...prev, confidence: v }))}
            />
          )}

          {/* Navigation */}
          <div className="flex justify-between items-center pt-2">
            <p className="text-xs text-gray-400">
              Step {currentStepIdx + 1} of {flow.total_steps}
            </p>
            {isLastStep ? (
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="flex items-center gap-2 px-6 py-2.5 text-sm font-semibold text-white bg-primary-600 rounded-xl hover:bg-primary-700 disabled:opacity-40 transition-colors"
              >
                {submitting ? 'Submitting…' : 'Submit & see result'}
              </button>
            ) : (
              <button
                onClick={handleNext}
                className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-primary-700 border border-primary-200 bg-primary-50 rounded-xl hover:bg-primary-100 transition-colors"
              >
                Next
                <ArrowRightIcon className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
