import type { PreviewResult, CommitResult } from '@/types/governance'
import ContentTypeBadge from './ContentTypeBadge'

// ── Preview result display ─────────────────────────────────────────────────

interface PreviewPanelProps {
  result: PreviewResult
}

export function ImportPreviewPanel({ result }: PreviewPanelProps) {
  const clean = result.invalid_rows === 0 && Object.keys(result.errors_by_file).length === 0

  return (
    <div className="space-y-5">
      {/* Summary banner */}
      <div
        className={`rounded-xl p-4 border ${
          clean ? 'bg-blue-50 border-blue-200' : 'bg-red-50 border-red-200'
        }`}
      >
        <div className="flex items-center gap-2 mb-3">
          <span
            className={`text-sm font-semibold ${clean ? 'text-blue-700' : 'text-red-700'}`}
          >
            {clean ? '✓ Preview clean — ready to commit' : '✗ Validation errors found'}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-gray-500 text-xs">Total rows</p>
            <p className="font-bold text-gray-900">{result.total_rows.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Valid rows</p>
            <p className="font-bold text-green-700">{result.valid_rows.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-gray-500 text-xs">Invalid rows</p>
            <p className={`font-bold ${result.invalid_rows > 0 ? 'text-red-600' : 'text-gray-400'}`}>
              {result.invalid_rows.toLocaleString()}
            </p>
          </div>
        </div>
      </div>

      {/* Detected content types */}
      {result.detected_content_types.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
            Detected content types
          </p>
          <div className="flex flex-wrap gap-2">
            {result.detected_content_types.map((ct) => (
              <ContentTypeBadge key={ct} contentType={ct} />
            ))}
          </div>
        </div>
      )}

      {/* Duplicate summary */}
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
          Duplicate detection
        </p>
        <div className="grid grid-cols-2 gap-2 text-xs">
          {[
            ['Within upload (ext ID)', result.duplicate_summary.duplicate_external_id_in_upload],
            ['Within upload (hash)', result.duplicate_summary.duplicate_hash_in_upload],
            ['Existing in DB (ext ID)', result.duplicate_summary.existing_external_id_in_db],
            ['Existing in DB (hash)', result.duplicate_summary.existing_hash_in_db],
          ].map(([label, count]) => (
            <div key={String(label)} className="flex justify-between bg-gray-50 rounded px-3 py-1.5">
              <span className="text-gray-500">{label}</span>
              <span className={Number(count) > 0 ? 'text-amber-600 font-medium' : 'text-gray-400'}>
                {count}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* File summaries table */}
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
          File breakdown
        </p>
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-xs">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-3 py-2 text-gray-500 font-medium">File</th>
                <th className="text-left px-3 py-2 text-gray-500 font-medium">Type</th>
                <th className="text-right px-3 py-2 text-gray-500 font-medium">Rows</th>
                <th className="text-right px-3 py-2 text-gray-500 font-medium">Valid</th>
                <th className="text-right px-3 py-2 text-gray-500 font-medium">Invalid</th>
                <th className="text-left px-3 py-2 text-gray-500 font-medium">Note</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {result.file_summaries.map((fs) => (
                <tr key={fs.file_name} className="hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono text-gray-700 max-w-[200px] truncate">
                    {fs.file_name}
                  </td>
                  <td className="px-3 py-2">
                    {fs.content_type ? (
                      <ContentTypeBadge contentType={fs.content_type} />
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right text-gray-700">{fs.total_rows}</td>
                  <td className="px-3 py-2 text-right text-green-700">{fs.valid_rows}</td>
                  <td className={`px-3 py-2 text-right ${fs.invalid_rows > 0 ? 'text-red-600 font-medium' : 'text-gray-400'}`}>
                    {fs.invalid_rows}
                  </td>
                  <td className="px-3 py-2 text-gray-400">
                    {fs.is_reference_only ? 'Reference only' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div>
          <p className="text-xs font-medium text-amber-600 uppercase tracking-wide mb-1">
            Warnings ({result.warnings.length})
          </p>
          <ul className="space-y-1">
            {result.warnings.slice(0, 10).map((w, i) => (
              <li key={i} className="text-xs text-amber-700 bg-amber-50 rounded px-3 py-1.5">
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Errors by file */}
      {Object.keys(result.errors_by_file).length > 0 && (
        <div>
          <p className="text-xs font-medium text-red-600 uppercase tracking-wide mb-1">
            File errors
          </p>
          {Object.entries(result.errors_by_file).map(([fname, errs]) => (
            <div key={fname} className="mb-2">
              <p className="text-xs font-semibold text-gray-700 mb-1">{fname}</p>
              <ul className="space-y-1">
                {errs.slice(0, 5).map((e, i) => (
                  <li key={i} className="text-xs text-red-700 bg-red-50 rounded px-3 py-1">
                    {e}
                  </li>
                ))}
                {errs.length > 5 && (
                  <li className="text-xs text-gray-400 px-3">+{errs.length - 5} more errors</li>
                )}
              </ul>
            </div>
          ))}
        </div>
      )}

      {/* Row errors */}
      {result.row_errors.length > 0 && (
        <div>
          <p className="text-xs font-medium text-red-600 uppercase tracking-wide mb-1">
            Row errors (first {Math.min(result.row_errors.length, 10)})
          </p>
          <div className="overflow-x-auto rounded border border-red-100">
            <table className="min-w-full text-xs">
              <thead className="bg-red-50">
                <tr>
                  <th className="text-left px-2 py-1.5 text-red-600 font-medium">File</th>
                  <th className="text-right px-2 py-1.5 text-red-600 font-medium">Row</th>
                  <th className="text-left px-2 py-1.5 text-red-600 font-medium">Code</th>
                  <th className="text-left px-2 py-1.5 text-red-600 font-medium">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-red-50">
                {result.row_errors.slice(0, 10).map((e, i) => (
                  <tr key={i}>
                    <td className="px-2 py-1 font-mono text-gray-600">{e.file_name}</td>
                    <td className="px-2 py-1 text-right text-gray-500">{e.row_number}</td>
                    <td className="px-2 py-1 text-red-600">{e.error_code}</td>
                    <td className="px-2 py-1 text-gray-700">{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* No auto-publish notice */}
      <div className="bg-gray-50 border border-gray-200 rounded-lg px-4 py-3 text-xs text-gray-600">
        <span className="font-semibold">Note:</span> Imported content is never auto-published.
        All items land in <span className="font-mono text-amber-700">pending_review</span> status
        until a clinical review approves them and an admin explicitly publishes to a region.
      </div>
    </div>
  )
}

// ── Commit result display ──────────────────────────────────────────────────

interface CommitPanelProps {
  result: CommitResult
}

export function CommitResultPanel({ result }: CommitPanelProps) {
  return (
    <div className="space-y-5">
      <div className="bg-green-50 border border-green-200 rounded-xl p-4">
        <p className="text-sm font-semibold text-green-700 mb-3">✓ Import committed successfully</p>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {[
            ['Content items created', result.created_items],
            ['Content versions created', result.created_versions],
            ['Evidence sources created', result.created_evidence_sources],
            ['Region rules created', result.created_region_rules],
            ['Skipped (duplicates)', result.skipped_duplicates],
            ['Invalid rows', result.invalid_rows],
          ].map(([label, value]) => (
            <div key={String(label)} className="flex justify-between bg-white rounded px-3 py-1.5 border border-green-100">
              <span className="text-gray-600 text-xs">{label}</span>
              <span className="font-bold text-gray-900">{value}</span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-gray-500">
          Import batch ID: <span className="font-mono">{result.import_batch_id}</span>
        </p>
      </div>

      {result.warnings.length > 0 && (
        <div>
          <p className="text-xs font-medium text-amber-600 uppercase tracking-wide mb-1">
            Warnings
          </p>
          <ul className="space-y-1">
            {result.warnings.slice(0, 10).map((w, i) => (
              <li key={i} className="text-xs text-amber-700 bg-amber-50 rounded px-3 py-1.5">
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-xs text-amber-700">
        <span className="font-semibold">Reminder:</span> No content has been published.
        Visit the <a href="/admin/governance/content" className="underline">Content Library</a> to
        submit clinical reviews and publish items to specific regions.
      </div>
    </div>
  )
}
