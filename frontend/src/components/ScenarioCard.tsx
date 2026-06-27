import { useNavigate } from 'react-router-dom'
import { BeakerIcon, ChatBubbleBottomCenterTextIcon } from '@heroicons/react/24/outline'
import { format } from 'date-fns'
import type { Scenario } from '@/types'
import DifficultyBadge from './DifficultyBadge'

interface Props {
  scenario: Scenario
}

export default function ScenarioCard({ scenario }: Props) {
  const navigate = useNavigate()
  const excerpt =
    scenario.clinical_case.length > 180
      ? scenario.clinical_case.slice(0, 180) + '…'
      : scenario.clinical_case

  return (
    <article className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow animate-fade-in">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-lg flex items-center justify-center">
            <BeakerIcon className="w-4 h-4 text-primary-600" />
          </div>
          <h3 className="text-sm font-semibold text-gray-900 truncate">{scenario.title}</h3>
        </div>
        <DifficultyBadge level={scenario.difficulty_level} />
      </div>

      {scenario.specialty && (
        <p className="mt-2 text-xs font-medium text-primary-600 uppercase tracking-wide">
          {scenario.specialty.replace(/-/g, ' ')}
        </p>
      )}

      <p className="mt-2 text-sm text-gray-600 leading-relaxed line-clamp-3">{excerpt}</p>

      {scenario.key_concepts && scenario.key_concepts.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {scenario.key_concepts.slice(0, 4).map((c) => (
            <span key={c} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-md">
              {c}
            </span>
          ))}
        </div>
      )}

      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center gap-1 text-xs text-gray-400">
          <ChatBubbleBottomCenterTextIcon className="w-3.5 h-3.5" />
          <span>{scenario.interaction_count} attempt{scenario.interaction_count !== 1 ? 's' : ''}</span>
          <span className="mx-1">·</span>
          <span>{format(new Date(scenario.created_at), 'MMM d, yyyy')}</span>
        </div>
        <button
          onClick={() => navigate(`/scenarios/${scenario.id}`)}
          className="px-3 py-1.5 bg-primary-600 text-white text-xs font-medium rounded-lg hover:bg-primary-700 transition-colors"
        >
          Start Case
        </button>
      </div>
    </article>
  )
}
