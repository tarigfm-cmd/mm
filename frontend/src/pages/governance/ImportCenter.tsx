import { useState } from 'react'
import toast from 'react-hot-toast'
import FileUploadPanel from '@/components/governance/FileUploadPanel'
import { ImportPreviewPanel, CommitResultPanel } from '@/components/governance/ImportPreviewTable'
import ConfirmActionDialog from '@/components/governance/ConfirmActionDialog'
import { importApi, approvalBatchApi } from '@/services/governanceApi'
import type { PreviewResult, CommitResult, ApprovalBatchRead } from '@/types/governance'
import { useEffect } from 'react'
import { InformationCircleIcon } from '@heroicons/react/24/outline'

type Step = 'upload' | 'previewing' | 'preview_done' | 'committing' | 'committed'

export default function ImportCenter() {
  const [file, setFile] = useState<File | null>(null)
  const [step, setStep] = useState<Step>('upload')
  const [previewResult, setPreviewResult] = useState<PreviewResult | null>(null)
  const [commitResult, setCommitResult] = useState<CommitResult | null>(null)
  const [approvalBatches, setApprovalBatches] = useState<ApprovalBatchRead[]>([])
  const [selectedBatchId, setSelectedBatchId] = useState<string>('')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [committing, setCommitting] = useState(false)

  useEffect(() => {
    approvalBatchApi.list().then(setApprovalBatches).catch(() => {})
  }, [])

  const handleFileChange = (f: File | null) => {
    setFile(f)
    setPreviewResult(null)
    setCommitResult(null)
    setStep('upload')
  }

  const handlePreview = async () => {
    if (!file) return
    setStep('previewing')
    try {
      const result = await importApi.preview(file)
      setPreviewResult(result)
      setStep('preview_done')
    } catch {
      toast.error('Preview failed. Check the file format and your permissions.')
      setStep('upload')
    }
  }

  const handleCommitConfirmed = async () => {
    if (!file) return
    setCommitting(true)
    try {
      const result = await importApi.commit(file, selectedBatchId || undefined)
      setCommitResult(result)
      setStep('committed')
      toast.success(`Import committed: ${result.created_items} items created.`)
    } catch {
      toast.error('Commit failed. See the error for details.')
    } finally {
      setCommitting(false)
      setConfirmOpen(false)
    }
  }

  const canPreview = file && step === 'upload'
  const previewClean =
    previewResult &&
    previewResult.invalid_rows === 0 &&
    Object.keys(previewResult.errors_by_file).length === 0
  const canCommit = step === 'preview_done' && previewClean

  const resetAll = () => {
    setFile(null)
    setPreviewResult(null)
    setCommitResult(null)
    setStep('upload')
    setSelectedBatchId('')
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-700">
        <InformationCircleIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold">Import flow: preview → approve → commit</p>
          <p className="mt-1 text-xs text-blue-600">
            Always run Preview first. Only commit after confirming zero errors.
            No content is published automatically — all items land in{' '}
            <span className="font-mono">pending_review</span>.
          </p>
        </div>
      </div>

      {/* Step 1 — File upload */}
      <section>
        <h2 className="text-sm font-semibold text-gray-700 mb-3">1. Select package file</h2>
        <FileUploadPanel
          file={file}
          onChange={handleFileChange}
          disabled={step === 'previewing' || step === 'committing' || step === 'committed'}
        />
      </section>

      {/* Step 2 — Preview */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-700">2. Validate (preview)</h2>
          <button
            onClick={handlePreview}
            disabled={!canPreview}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {step === 'previewing' ? 'Previewing…' : 'Run Preview'}
          </button>
        </div>

        {step === 'previewing' && (
          <div className="flex items-center gap-3 text-sm text-gray-500 py-4">
            <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            Validating package — this may take a moment for large files…
          </div>
        )}

        {previewResult && <ImportPreviewPanel result={previewResult} />}
      </section>

      {/* Step 3 — Approval batch (optional) */}
      {step === 'preview_done' && previewClean && (
        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">
            3. Link approval batch (optional)
          </h2>
          <p className="text-xs text-gray-500 mb-2">
            If this package was externally approved by a pharmacist team, link the approval batch so
            imported items can receive <span className="font-mono">clinically_approved</span> status.
            Leave blank to import as <span className="font-mono">pending_review</span>.
          </p>
          {approvalBatches.length === 0 ? (
            <p className="text-xs text-gray-400">
              No approval batches found.{' '}
              <a href="/admin/governance/approval-batches" className="text-primary-600 hover:underline">
                Create one first.
              </a>
            </p>
          ) : (
            <select
              value={selectedBatchId}
              onChange={(e) => setSelectedBatchId(e.target.value)}
              className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">— No approval batch (import as pending_review) —</option>
              {approvalBatches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.batch_name} · {b.approved_by_team_name} · {new Date(b.approved_at).toLocaleDateString()}
                </option>
              ))}
            </select>
          )}
        </section>
      )}

      {/* Step 4 — Commit */}
      {step === 'preview_done' && (
        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">4. Commit to database</h2>
          {!previewClean ? (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              Fix validation errors before committing.
            </div>
          ) : (
            <div className="flex items-center justify-between p-4 bg-amber-50 border border-amber-200 rounded-xl">
              <div>
                <p className="text-sm font-semibold text-amber-800">Ready to commit</p>
                <p className="text-xs text-amber-700 mt-0.5">
                  {(previewResult?.valid_rows ?? 0).toLocaleString()} rows ·{' '}
                  {selectedBatchId ? 'Linked to approval batch' : 'No approval batch (pending_review)'}
                </p>
              </div>
              <button
                onClick={() => setConfirmOpen(true)}
                disabled={!canCommit}
                className="px-5 py-2 text-sm font-semibold text-white bg-amber-500 rounded-lg hover:bg-amber-600 disabled:opacity-40 transition-colors"
              >
                Commit Import
              </button>
            </div>
          )}
        </section>
      )}

      {/* Commit result */}
      {commitResult && <CommitResultPanel result={commitResult} />}

      {/* Reset */}
      {step === 'committed' && (
        <button
          onClick={resetAll}
          className="text-sm text-primary-600 hover:underline"
        >
          Import another package
        </button>
      )}

      {/* Confirm dialog */}
      <ConfirmActionDialog
        open={confirmOpen}
        title="Commit import to database?"
        description={
          <div className="space-y-2">
            <p>
              This will write{' '}
              <strong>{(previewResult?.valid_rows ?? 0).toLocaleString()}</strong> governance records
              from <strong>{file?.name}</strong> into the database.
            </p>
            <p className="text-amber-600">
              No content will be published. All items land in{' '}
              <span className="font-mono font-semibold">pending_review</span>.
            </p>
            <p>This action cannot be undone, though duplicates are skipped on re-import.</p>
          </div>
        }
        confirmLabel="Commit Import"
        confirmVariant="warning"
        loading={committing}
        onConfirm={handleCommitConfirmed}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  )
}
