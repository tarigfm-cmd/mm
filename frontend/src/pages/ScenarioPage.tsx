import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeftIcon,
  PaperAirplaneIcon,
  LightBulbIcon,
  BookOpenIcon,
} from '@heroicons/react/24/outline'
import { scenariosApi, getOrCreateSessionId } from '@/services/api'
import { useScenarioStore } from '@/store/appStore'
import MessageBubble from '@/components/MessageBubble'
import DifficultyBadge from '@/components/DifficultyBadge'
import LoadingSpinner from '@/components/LoadingSpinner'
import toast from 'react-hot-toast'

export default function ScenarioPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const {
    currentScenario,
    currentInteractions,
    interactionsLoading,
    answerSubmitting,
    setCurrentScenario,
    setCurrentInteractions,
    appendInteraction,
    setInteractionsLoading,
    setAnswerSubmitting,
  } = useScenarioStore()

  const [answer, setAnswer] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!id) return
    loadScenario(id)
  }, [id])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentInteractions])

  const loadScenario = async (scenarioId: string) => {
    setInteractionsLoading(true)
    try {
      const res = await scenariosApi.getInteractions(scenarioId)
      setCurrentScenario(res.scenario)
      setCurrentInteractions(res.interactions)
    } catch {
      toast.error('Scenario not found.')
      navigate('/scenarios')
    } finally {
      setInteractionsLoading(false)
    }
  }

  const handleSubmit = async () => {
    if (!answer.trim() || !currentScenario || !id) return
    if (answer.trim().length < 10) {
      toast.error('Please provide a more detailed answer.')
      return
    }

    const text = answer.trim()
    setAnswer('')
    setAnswerSubmitting(true)

    try {
      const interaction = await scenariosApi.submitAnswer(id, {
        scenario_id: id,
        content: text,
        session_id: getOrCreateSessionId(),
      })
      appendInteraction(interaction)
    } catch {
      setAnswer(text) // restore on error
    } finally {
      setAnswerSubmitting(false)
      textareaRef.current?.focus()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleSubmit()
    }
  }

  if (interactionsLoading || !currentScenario) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner label="Loading scenario…" />
      </div>
    )
  }

  const avgScore =
    currentInteractions.length > 0
      ? currentInteractions.reduce((s, i) => s + (i.score ?? 0), 0) / currentInteractions.length
      : null

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] -mt-8 -mx-8">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-8 py-4">
        <div className="flex items-start gap-4">
          <button
            onClick={() => navigate('/scenarios')}
            className="mt-0.5 p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ArrowLeftIcon className="w-4 h-4" />
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-lg font-semibold text-gray-900 truncate">
                {currentScenario.title}
              </h1>
              <DifficultyBadge level={currentScenario.difficulty_level} />
              {currentScenario.specialty && (
                <span className="text-xs text-primary-600 font-medium">
                  {currentScenario.specialty.replace(/-/g, ' ')}
                </span>
              )}
            </div>
            {avgScore !== null && (
              <p className="text-xs text-gray-400 mt-0.5">
                Average score: {Math.round(avgScore * 100)}% across {currentInteractions.length} attempt{currentInteractions.length !== 1 ? 's' : ''}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Case panel */}
        <aside className="w-96 flex-shrink-0 border-r border-gray-200 bg-gray-50 overflow-y-auto px-6 py-6">
          <div className="flex items-center gap-2 mb-4">
            <BookOpenIcon className="w-4 h-4 text-primary-600" />
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Clinical Case
            </h2>
          </div>
          <div className="prose prose-sm max-w-none text-gray-700 leading-relaxed whitespace-pre-wrap">
            {currentScenario.clinical_case}
          </div>

          {currentScenario.key_concepts && currentScenario.key_concepts.length > 0 && (
            <div className="mt-6 pt-5 border-t border-gray-200">
              <div className="flex items-center gap-2 mb-2">
                <LightBulbIcon className="w-4 h-4 text-amber-500" />
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  Key Concepts
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {currentScenario.key_concepts.map((c) => (
                  <span key={c} className="px-2 py-0.5 bg-white border border-gray-200 text-gray-600 text-xs rounded-md">
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )}
        </aside>

        {/* Chat panel */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
            {currentInteractions.length === 0 && (
              <div className="text-center py-12">
                <PaperAirplaneIcon className="mx-auto h-10 w-10 text-gray-300 mb-3" />
                <p className="text-sm font-medium text-gray-500">Ready when you are</p>
                <p className="text-xs text-gray-400 mt-1">
                  Read the case on the left, then type your clinical response below.
                </p>
              </div>
            )}

            {currentInteractions.map((interaction) => (
              <MessageBubble key={interaction.id} interaction={interaction} />
            ))}

            {answerSubmitting && (
              <div className="flex justify-center py-4">
                <LoadingSpinner size="sm" label="AI is reviewing your answer…" />
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Answer input */}
          <div className="flex-shrink-0 border-t border-gray-200 bg-white px-6 py-4">
            <div className="flex gap-3">
              <textarea
                ref={textareaRef}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={answerSubmitting}
                rows={3}
                placeholder="Write your clinical assessment and management plan… (Ctrl+Enter to submit)"
                className="flex-1 px-4 py-3 border border-gray-300 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-50"
              />
              <button
                onClick={handleSubmit}
                disabled={answerSubmitting || !answer.trim()}
                className="flex-shrink-0 self-end px-4 py-3 bg-primary-600 text-white rounded-xl hover:bg-primary-700 disabled:opacity-40 transition-colors"
                title="Submit answer (Ctrl+Enter)"
              >
                <PaperAirplaneIcon className="w-5 h-5" />
              </button>
            </div>
            <p className="mt-1.5 text-xs text-gray-400">
              Tip: Be specific — mention drug names, doses, monitoring parameters, and patient counselling points.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
