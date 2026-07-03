import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { PlusIcon, CheckBadgeIcon } from '@heroicons/react/24/outline'
import { approvalBatchApi } from '@/services/governanceApi'
import RegionBadge from '@/components/governance/RegionBadge'
import type { ApprovalBatchCreate, ApprovalBatchRead } from '@/types/governance'

const REGIONS = ['UK', 'US', 'GCC', 'AU'] as const

const EMPTY_FORM: ApprovalBatchCreate = {
  batch_name: '',
  source_package_name: '',
  approved_by_team_name: '',
  approval_statement: '',
  approved_at: new Date().toISOString().slice(0, 16),
  region_scope: [],
  content_count: undefined,
  notes: '',
  signed_manifest_hash: '',
}

export default function ApprovalBatchesPage() {
  const [batches, setBatches] = useState<ApprovalBatchRead[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<ApprovalBatchCreate>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const data = await approvalBatchApi.list()
      setBatches(data)
    } catch {
      toast.error('Failed to load approval batches.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const toggleRegion = (r: string) => {
    setForm((f) => ({
      ...f,
      region_scope: f.region_scope?.includes(r)
        ? f.region_scope.filter((x) => x !== r)
        : [...(f.region_scope ?? []), r],
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload: ApprovalBatchCreate = {
        ...form,
        approved_at: new Date(form.approved_at).toISOString(),
        content_count: form.content_count ?? undefined,
        source_package_name: form.source_package_name || undefined,
        approval_statement: form.approval_statement || undefined,
        notes: form.notes || undefined,
        signed_manifest_hash: form.signed_manifest_hash || undefined,
      }
      const created = await approvalBatchApi.create(payload)
      setBatches((prev) => [created, ...prev])
      toast.success('Approval batch created.')
      setShowForm(false)
      setForm(EMPTY_FORM)
    } catch {
      toast.error('Failed to create approval batch. Check required fields.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-500 mt-0.5">
            Approval batches record team-level pharmacist sign-offs on content packages.
            Link a batch ID during import to mark items as{' '}
            <span className="font-mono">clinically_approved</span>.
          </p>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
        >
          <PlusIcon className="w-4 h-4" />
          New Batch
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-white border border-gray-200 rounded-xl p-6 space-y-4"
        >
          <h3 className="text-sm font-semibold text-gray-800">New approval batch</h3>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Batch name <span className="text-red-500">*</span>
              </label>
              <input
                required
                type="text"
                value={form.batch_name}
                onChange={(e) => setForm((f) => ({ ...f, batch_name: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="e.g. CP Content Bank v2 — UK Pharmacist Review"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Source package name
              </label>
              <input
                type="text"
                value={form.source_package_name ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, source_package_name: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="e.g. community_pharmacy_mega_content_bank_v2"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Approved by team <span className="text-red-500">*</span>
              </label>
              <input
                required
                type="text"
                value={form.approved_by_team_name}
                onChange={(e) => setForm((f) => ({ ...f, approved_by_team_name: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="e.g. Clinical Pharmacy Review Board"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Approved at <span className="text-red-500">*</span>
              </label>
              <input
                required
                type="datetime-local"
                value={form.approved_at}
                onChange={(e) => setForm((f) => ({ ...f, approved_at: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Approval statement
            </label>
            <textarea
              rows={2}
              value={form.approval_statement ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, approval_statement: e.target.value }))}
              className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
              placeholder="Brief statement of what was approved"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-2">Region scope</label>
              <div className="flex gap-2 flex-wrap">
                {REGIONS.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => toggleRegion(r)}
                    className={`px-3 py-1 text-xs font-semibold rounded-full border transition-colors ${
                      form.region_scope?.includes(r)
                        ? 'bg-primary-600 text-white border-primary-600'
                        : 'bg-white text-gray-600 border-gray-300 hover:border-primary-400'
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Content count</label>
              <input
                type="number"
                min={0}
                value={form.content_count ?? ''}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    content_count: e.target.value ? parseInt(e.target.value) : undefined,
                  }))
                }
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="e.g. 11500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Signed manifest hash (optional)
            </label>
            <input
              type="text"
              value={form.signed_manifest_hash ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, signed_manifest_hash: e.target.value }))}
              className="w-full text-sm font-mono border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="SHA-256 hash of the signed package manifest"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2 border-t border-gray-100">
            <button
              type="button"
              onClick={() => { setShowForm(false); setForm(EMPTY_FORM) }}
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Create Batch'}
            </button>
          </div>
        </form>
      )}

      {/* Batch list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 animate-pulse rounded-xl" />
          ))}
        </div>
      ) : batches.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <CheckBadgeIcon className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No approval batches yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {batches.map((b) => (
            <div
              key={b.id}
              className="bg-white border border-gray-200 rounded-xl p-5 space-y-2"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 truncate">{b.batch_name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {b.approved_by_team_name} ·{' '}
                    {new Date(b.approved_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {b.content_count != null && (
                    <span className="text-xs text-gray-500">{b.content_count.toLocaleString()} items</span>
                  )}
                  {b.region_scope?.map((r) => <RegionBadge key={r} region={r} />)}
                </div>
              </div>

              {b.approval_statement && (
                <p className="text-xs text-gray-600 italic">{b.approval_statement}</p>
              )}

              {b.source_package_name && (
                <p className="text-xs text-gray-400">
                  Package: <span className="font-mono">{b.source_package_name}</span>
                </p>
              )}

              <div className="flex items-center justify-between pt-1 border-t border-gray-50">
                <p className="text-xs text-gray-300 font-mono">ID: {b.id}</p>
                {b.signed_manifest_hash && (
                  <p className="text-xs text-gray-300 font-mono truncate max-w-[200px]">
                    hash: {b.signed_manifest_hash.slice(0, 12)}…
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
