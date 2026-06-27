import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DocumentTextIcon,
  BeakerIcon,
  ChatBubbleBottomCenterTextIcon,
  ArrowRightIcon,
  ArrowUpTrayIcon,
} from '@heroicons/react/24/outline'
import { materialsApi, scenariosApi } from '@/services/api'
import { useScenarioStore } from '@/store/scenarioStore'
import ScenarioCard from '@/components/ScenarioCard'
import LoadingSpinner from '@/components/LoadingSpinner'

interface Stats {
  materials: number
  scenarios: number
  interactions: number
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { scenarios, setScenariosLoading, setScenarios, scenariosLoading } =
    useScenarioStore()
  const [stats, setStats] = useState<Stats>({ materials: 0, scenarios: 0, interactions: 0 })
  const [statsLoading, setStatsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const [mats, scens] = await Promise.all([
          materialsApi.list(1, 1),
          scenariosApi.list({ page: 1, per_page: 6 }),
        ])
        if (cancelled) return
        setStats({
          materials: mats.total,
          scenarios: scens.total,
          interactions: scens.items.reduce((sum, s) => sum + s.interaction_count, 0),
        })
        setScenarios(scens.items, scens.total)
      } finally {
        if (!cancelled) setStatsLoading(false)
      }
    }

    setScenariosLoading(true)
    load().finally(() => setScenariosLoading(false))
    return () => { cancelled = true }
  }, [])

  const statCards = [
    {
      label: 'Materials',
      value: stats.materials,
      icon: DocumentTextIcon,
      color: 'bg-blue-50 text-blue-600',
      action: () => navigate('/upload'),
    },
    {
      label: 'Scenarios',
      value: stats.scenarios,
      icon: BeakerIcon,
      color: 'bg-primary-50 text-primary-600',
      action: () => navigate('/scenarios'),
    },
    {
      label: 'Attempts',
      value: stats.interactions,
      icon: ChatBubbleBottomCenterTextIcon,
      color: 'bg-clinical-50 text-clinical-600',
      action: undefined,
    },
  ]

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="bg-gradient-to-r from-primary-700 to-primary-500 rounded-2xl px-8 py-8 text-white">
        <h1 className="text-2xl font-bold">Welcome back</h1>
        <p className="mt-1 text-primary-100 text-sm">
          Your AI-powered pharmacy clinical training platform
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            onClick={() => navigate('/upload')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white text-primary-700 font-medium text-sm rounded-lg hover:bg-primary-50 transition-colors"
          >
            <ArrowUpTrayIcon className="w-4 h-4" />
            Upload Material
          </button>
          <button
            onClick={() => navigate('/scenarios')}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary-600 border border-primary-400 text-white font-medium text-sm rounded-lg hover:bg-primary-500 transition-colors"
          >
            <BeakerIcon className="w-4 h-4" />
            Browse Scenarios
          </button>
        </div>
      </div>

      {/* Stats */}
      {statsLoading ? (
        <LoadingSpinner label="Loading stats…" />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {statCards.map(({ label, value, icon: Icon, color, action }) => (
            <button
              key={label}
              onClick={action}
              disabled={!action}
              className="text-left bg-white rounded-xl border border-gray-200 p-5 hover:shadow-sm transition-shadow disabled:cursor-default"
            >
              <div className={`inline-flex p-2 rounded-lg ${color}`}>
                <Icon className="w-5 h-5" />
              </div>
              <p className="mt-3 text-2xl font-bold text-gray-900">{value}</p>
              <p className="text-sm text-gray-500">{label}</p>
            </button>
          ))}
        </div>
      )}

      {/* Recent Scenarios */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">Recent Scenarios</h2>
          <button
            onClick={() => navigate('/scenarios')}
            className="inline-flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            View all
            <ArrowRightIcon className="w-3.5 h-3.5" />
          </button>
        </div>

        {scenariosLoading ? (
          <LoadingSpinner label="Loading scenarios…" />
        ) : scenarios.length === 0 ? (
          <EmptyScenarios />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {scenarios.slice(0, 4).map((s) => (
              <ScenarioCard key={s.id} scenario={s} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function EmptyScenarios() {
  const navigate = useNavigate()
  return (
    <div className="text-center py-16 bg-gray-50 rounded-xl border border-dashed border-gray-300">
      <BeakerIcon className="mx-auto h-10 w-10 text-gray-300 mb-3" />
      <p className="text-sm font-medium text-gray-500">No scenarios yet</p>
      <p className="text-xs text-gray-400 mt-1">Upload a study material to generate your first case</p>
      <button
        onClick={() => navigate('/upload')}
        className="mt-4 px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 transition-colors"
      >
        Get started
      </button>
    </div>
  )
}
