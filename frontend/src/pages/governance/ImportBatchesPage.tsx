import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpTrayIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'
import { importBatchApi } from '@/services/governanceApi'
import type { ImportBatchRead } from '@/types/governance'

function BatchStatusBadge({ status }: { status: string }) {
  const cls =
    status === 'committed'
      ? 'bg-green-100 text-green-700'
      : 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {status}
    </span>
  )
}

export default function ImportBatchesPage() {
  const [batches, setBatches] = useState<ImportBatchRead[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    importBatchApi
      .list(100)
      .then((r) => {
        setBatches(r.items)
        setTotal(r.total)
      })
      .catch(() => setError('Failed to load import batches. Check your permissions.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-400">
            {loading ? 'Loading…' : `${total.toLocaleString()} import batch${total !== 1 ? 'es' : ''}`}
          </p>
        </div>
        <Link
          to="/admin/governance/import"
          className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <ArrowUpTrayIcon className="w-3 h-3" />
          New Import
        </Link>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {!loading && batches.length === 0 && !error && (
        <div className="text-center py-12 text-gray-400">
          <ArrowUpTrayIcon className="w-8 h-8 mx-auto mb-3 text-gray-300" />
          <p className="text-sm">No import batches yet.</p>
          <Link to="/admin/governance/import" className="mt-2 text-xs text-primary-600 hover:underline block">
            Run the first import →
          </Link>
        </div>
      )}

      {(loading || batches.length > 0) && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Source file</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Status</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Total</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Valid</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Invalid</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Skipped</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Items</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Versions</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Evidence</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Rules</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Imported at</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Committed at</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading
                  ? Array.from({ length: 4 }).map((_, i) => (
                      <tr key={i}>
                        {Array.from({ length: 13 }).map((__, j) => (
                          <td key={j} className="px-4 py-3">
                            <div className="h-3 bg-gray-100 animate-pulse rounded" />
                          </td>
                        ))}
                      </tr>
                    ))
                  : batches.map((b) => (
                      <tr key={b.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-3 font-mono text-xs text-gray-700 max-w-[200px]">
                          <span className="block truncate" title={b.source_file_name}>
                            {b.source_file_name}
                          </span>
                          <span className="text-gray-400">{b.package_type.toUpperCase()}</span>
                        </td>
                        <td className="px-4 py-3">
                          <BatchStatusBadge status={b.status} />
                        </td>
                        <td className="px-4 py-3 text-right text-xs text-gray-600">{b.total_rows.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right text-xs text-green-700 font-medium">{b.valid_rows.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right text-xs text-red-600">{b.invalid_rows.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right text-xs text-gray-500">{b.skipped_duplicates.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right text-xs font-semibold text-gray-800">{b.created_items.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right text-xs text-gray-600">{b.created_versions.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right text-xs text-gray-600">{b.created_evidence_sources.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right text-xs text-gray-600">{b.created_region_rules.toLocaleString()}</td>
                        <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                          {new Date(b.created_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                          {b.committed_at ? new Date(b.committed_at).toLocaleString() : '—'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Link
                            to={`/admin/governance/import/batches/${b.id}`}
                            className="text-xs text-primary-600 hover:underline font-medium whitespace-nowrap"
                          >
                            Details →
                          </Link>
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && total > 100 && (
        <p className="text-xs text-gray-400 text-center">
          Showing most recent 100 of {total.toLocaleString()} batches.
        </p>
      )}
    </div>
  )
}
