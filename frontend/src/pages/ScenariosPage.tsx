import { useEffect, useState } from 'react'
import { BeakerIcon, FunnelIcon } from '@heroicons/react/24/outline'
import { scenariosApi } from '@/services/api'
import { useScenarioStore } from '@/store/scenarioStore'
import ScenarioCard from '@/components/ScenarioCard'
import LoadingSpinner from '@/components/LoadingSpinner'

export default function ScenariosPage() {
  const { scenarios, scenariosTotal, setScenarios, scenariosLoading, setScenariosLoading } =
    useScenarioStore()
  const [difficulty, setDifficulty] = useState<string>('')
  const [page, setPage] = useState(1)
  const perPage = 12

  useEffect(() => {
    loadScenarios()
  }, [difficulty, page])

  const loadScenarios = async () => {
    setScenariosLoading(true)
    try {
      const res = await scenariosApi.list({
        page,
        per_page: perPage,
        difficulty: difficulty || undefined,
      })
      setScenarios(res.items, res.total)
    } finally {
      setScenariosLoading(false)
    }
  }

  const totalPages = Math.ceil(scenariosTotal / perPage)

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Clinical Scenarios</h1>
          <p className="mt-1 text-sm text-gray-500">
            {scenariosTotal} scenario{scenariosTotal !== 1 ? 's' : ''} available
          </p>
        </div>

        <div className="flex items-center gap-2">
          <FunnelIcon className="w-4 h-4 text-gray-400" />
          <select
            value={difficulty}
            onChange={(e) => { setDifficulty(e.target.value); setPage(1) }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All levels</option>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>
      </div>

      {scenariosLoading ? (
        <LoadingSpinner label="Loading scenarios…" />
      ) : scenarios.length === 0 ? (
        <div className="text-center py-20 bg-gray-50 rounded-xl border border-dashed border-gray-300">
          <BeakerIcon className="mx-auto h-12 w-12 text-gray-300 mb-3" />
          <p className="text-sm font-medium text-gray-500">No scenarios found</p>
          <p className="text-xs text-gray-400 mt-1">
            {difficulty ? 'Try a different difficulty level.' : 'Upload a material to generate your first scenario.'}
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {scenarios.map((s) => (
              <ScenarioCard key={s.id} scenario={s} />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex justify-center gap-2 pt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 transition-colors"
              >
                Previous
              </button>
              <span className="px-3 py-1.5 text-sm text-gray-600">
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
