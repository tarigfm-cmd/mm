import ReactMarkdown from 'react-markdown'
import { UserIcon, CpuChipIcon } from '@heroicons/react/24/solid'
import { format } from 'date-fns'
import type { Interaction } from '@/types'

interface Props {
  interaction: Interaction
}

function ScoreMeter({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color =
    pct >= 75 ? 'bg-clinical-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2 mt-2">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold text-gray-700">{pct}%</span>
    </div>
  )
}

export default function MessageBubble({ interaction }: Props) {
  const score = interaction.score

  return (
    <div className="space-y-4 animate-slide-up">
      {/* User answer */}
      <div className="flex gap-3 justify-end">
        <div className="max-w-2xl">
          <div className="bg-primary-600 text-white rounded-2xl rounded-tr-md px-4 py-3 text-sm leading-relaxed">
            {interaction.user_answer}
          </div>
          <p className="mt-1 text-xs text-gray-400 text-right">
            {format(new Date(interaction.created_at), 'HH:mm')}
          </p>
        </div>
        <div className="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
          <UserIcon className="w-4 h-4 text-primary-600" />
        </div>
      </div>

      {/* AI feedback */}
      <div className="flex gap-3">
        <div className="flex-shrink-0 w-8 h-8 bg-clinical-100 rounded-full flex items-center justify-center">
          <CpuChipIcon className="w-4 h-4 text-clinical-600" />
        </div>
        <div className="max-w-2xl flex-1">
          <div className="bg-gray-50 border border-gray-200 rounded-2xl rounded-tl-md px-4 py-3">
            {score !== null && (
              <div className="mb-3 pb-3 border-b border-gray-200">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
                  Score
                </p>
                <ScoreMeter score={score} />
              </div>
            )}

            <div className="text-sm text-gray-700 leading-relaxed prose prose-sm max-w-none">
              <ReactMarkdown>{interaction.ai_feedback}</ReactMarkdown>
            </div>

            {interaction.strengths && interaction.strengths.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                <p className="text-xs font-semibold text-clinical-700 mb-1.5">Strengths</p>
                <ul className="space-y-1">
                  {interaction.strengths.map((s, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-xs text-gray-600">
                      <span className="text-clinical-500 mt-0.5">✓</span>
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {interaction.areas_for_improvement && interaction.areas_for_improvement.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                <p className="text-xs font-semibold text-amber-700 mb-1.5">Areas to develop</p>
                <ul className="space-y-1">
                  {interaction.areas_for_improvement.map((a, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-xs text-gray-600">
                      <span className="text-amber-500 mt-0.5">→</span>
                      {a}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {interaction.next_steps && interaction.next_steps.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-200">
                <p className="text-xs font-semibold text-primary-700 mb-1.5">Next steps</p>
                <ul className="space-y-1">
                  {interaction.next_steps.map((n, i) => (
                    <li key={i} className="flex items-start gap-1.5 text-xs text-gray-600">
                      <span className="text-primary-400 mt-0.5">•</span>
                      {n}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
