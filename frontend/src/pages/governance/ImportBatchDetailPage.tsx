import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeftIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline'
import { importBatchApi } from '@/services/governanceApi'
import type { ImportBatchRead } from '@/types/governance'

function Stat({ label, value, accent }: { label: string; value: React.ReactNode; accent?: string }) {
  const valueClass = accent === 'green'
    ? 'text-green-700 font-semibold'
    : accent === 'red'
    ? 'text-red-600 font-semibold'
    : 'text-gray-900 font-semibold'
  return (
    <div className="bg-gray-50 rounded-lg px-4 py-3">
      <p className="text-xs text-gray-500 mb-0.5">{label}</p>
      <p className={`text-lg ${valueClass}`}>{value}</p>
    </div>
  )
}

export default function ImportBatchDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [batch, setBatch] = useState<ImportBatchRead | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    importBatchApi
      .get(id)
      .then(setBatch)
      .catch(() => setError('Import batch not found or you lack permission.'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-4 w-32 bg-gray-100 rounded" />
        <div className="h-48 bg-gray-100 rounded-xl" />
      </div>
    )
  }

  if (error || !batch) {
    return (
      <div className="text-center py-12 text-gray-400">
        <ExclamationCircleIcon className="w-8 h-8 mx-auto mb-3 text-gray-300" />
        <p className="text-sm">{error ?? 'Batch not found.'}</p>
        <Link
          to="/admin/governance/import/batches"
          className="mt-2 text-xs text-primary-600 hover:underline block"
        >
          ← Import History
        </Link>
      </div>
    )
  }

  const warnings = batch.warnings_json ?? []
  const hasWarnings = warnings.length > 0
  const isClean = batch.invalid_rows === 0 && batch.skipped_duplicates === 0

  return (
    <div className="max-w-4xl space-y-6">
      {/* Breadcrumb */}
      <Link
        to="/admin/governance/import/batches"
        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 w-fit"
      >
        <ArrowLeftIcon className="w-3 h-3" /> Import History
      </Link>

      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs text-gray-400 font-mono mb-1">{batch.id}</p>
            <h2
              className="text-lg font-bold text-gray-900 font-mono truncate"
              title={batch.source_file_name}
            >
              {batch.source_file_name}
            </h2>
            <div className="flex items-center gap-3 mt-2">
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${
                  batch.status === 'committed'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {batch.status === 'committed' && <CheckCircleIcon className="w-3 h-3" />}
                {batch.status}
              </span>
              <span className="text-xs text-gray-400 uppercase">{batch.package_type}</span>
            </div>
          </div>
          <div className="text-right text-xs text-gray-400 flex-shrink-0">
            <p>Imported {new Date(batch.created_at).toLocaleString()}</p>
            {batch.committed_at && (
              <p className="mt-0.5">Committed {new Date(batch.committed_at).toLocaleString()}</p>
            )}
          </div>
        </div>
      </div>

      {/* Learner visibility notice */}
      <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-700">
        <InformationCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
        <p className="text-xs">
          Imported content is <strong>not learner-visible</strong>. All items land in{' '}
          <span className="font-mono">pending_review</span> status. Publication requires clinical
          review and explicit admin action per region.
        </p>
      </div>

      {/* Row counts grid */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Row counts</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          <Stat label="Total rows" value={batch.total_rows.toLocaleString()} />
          <Stat label="Valid rows" value={batch.valid_rows.toLocaleString()} accent="green" />
          <Stat label="Invalid rows" value={batch.invalid_rows.toLocaleString()} accent={batch.invalid_rows > 0 ? 'red' : undefined} />
          <Stat label="Skipped duplicates" value={batch.skipped_duplicates.toLocaleString()} />
        </div>
      </section>

      {/* Created records grid */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Records created</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Stat label="Content items" value={batch.created_items.toLocaleString()} accent="green" />
          <Stat label="Versions" value={batch.created_versions.toLocaleString()} />
          <Stat label="Evidence sources" value={batch.created_evidence_sources.toLocaleString()} />
          <Stat label="Region rules" value={batch.created_region_rules.toLocaleString()} />
        </div>
      </section>

      {/* Duplicate/skip summary */}
      {!isClean && (
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Duplicate / skip summary</h3>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800 space-y-1">
            {batch.invalid_rows > 0 && (
              <p>
                <span className="font-semibold">{batch.invalid_rows.toLocaleString()}</span> row
                {batch.invalid_rows !== 1 ? 's' : ''} failed validation and were not imported.
              </p>
            )}
            {batch.skipped_duplicates > 0 && (
              <p>
                <span className="font-semibold">{batch.skipped_duplicates.toLocaleString()}</span> row
                {batch.skipped_duplicates !== 1 ? 's' : ''} were skipped as duplicates (same
                external_id or content_hash already in database).
              </p>
            )}
          </div>
        </section>
      )}

      {/* Approval batch link */}
      {batch.approval_batch_id && (
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Linked approval batch</h3>
          <Link
            to="/admin/governance/approval-batches"
            className="text-xs font-mono text-primary-600 hover:underline"
          >
            {batch.approval_batch_id}
          </Link>
        </section>
      )}

      {/* Warnings */}
      {hasWarnings && (
        <section>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Import warnings ({warnings.length})</h3>
          <ul className="space-y-1">
            {warnings.map((w, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                <ExclamationCircleIcon className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-amber-500" />
                {w}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
