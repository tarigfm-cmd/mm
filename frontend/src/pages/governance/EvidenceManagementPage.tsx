import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { PlusIcon, BookOpenIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline'
import { evidenceApi } from '@/services/governanceApi'
import EvidenceStatusBadge from '@/components/governance/EvidenceStatusBadge'
import RegionBadge from '@/components/governance/RegionBadge'
import type { EvidenceSourceCreate, EvidenceSourceRead, EvidenceSourceUpdate } from '@/types/governance'

const REGIONS = ['', 'UK', 'US', 'GCC', 'AU', 'GLOBAL']
const EVIDENCE_STATUSES = ['', 'active', 'needs_review', 'superseded', 'region_specific', 'retired']

const EMPTY_FORM: EvidenceSourceCreate = {
  title: '',
  organization: '',
  source_type: '',
  url: '',
  region: '',
  evidence_status: 'active',
  notes: '',
}

export default function EvidenceManagementPage() {
  const [sources, setSources] = useState<EvidenceSourceRead[]>([])
  const [due, setDue] = useState<EvidenceSourceRead[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<EvidenceSourceCreate>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<EvidenceSourceUpdate>({})

  // Filters
  const [regionFilter, setRegionFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [showDue, setShowDue] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [allSources, dueList] = await Promise.all([
        evidenceApi.list({
          region: regionFilter || undefined,
          evidence_status: statusFilter || undefined,
        }),
        evidenceApi.dueForReview().catch(() => [] as EvidenceSourceRead[]),
      ])
      setSources(allSources)
      setDue(dueList)
    } catch {
      toast.error('Failed to load evidence sources.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [regionFilter, statusFilter]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload: EvidenceSourceCreate = {
        ...form,
        region: form.region || undefined,
        organization: form.organization || undefined,
        source_type: form.source_type || undefined,
        url: form.url || undefined,
        notes: form.notes || undefined,
      }
      const created = await evidenceApi.create(payload)
      setSources((prev) => [created, ...prev])
      toast.success('Evidence source created.')
      setShowForm(false)
      setForm(EMPTY_FORM)
    } catch {
      toast.error('Failed to create evidence source.')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdate = async (id: string) => {
    setSaving(true)
    try {
      const updated = await evidenceApi.update(id, editForm)
      setSources((prev) => prev.map((s) => (s.id === id ? updated : s)))
      toast.success('Evidence source updated.')
      setEditId(null)
      setEditForm({})
    } catch {
      toast.error('Failed to update evidence source.')
    } finally {
      setSaving(false)
    }
  }

  const displaySources = showDue ? due : sources

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Due for review alert */}
      {due.length > 0 && (
        <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <ExclamationCircleIcon className="w-5 h-5 text-amber-500 flex-shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-amber-800">
              {due.length} source{due.length !== 1 ? 's' : ''} overdue for review
            </p>
            <p className="text-xs text-amber-600">
              Update their status or next review date after verification.
            </p>
          </div>
          <button
            onClick={() => setShowDue((s) => !s)}
            className="text-xs font-medium text-amber-700 hover:underline flex-shrink-0"
          >
            {showDue ? 'Show all' : 'Show due only'}
          </button>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap items-end gap-3 justify-between">
        <div className="flex flex-wrap gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Region</label>
            <select
              value={regionFilter}
              onChange={(e) => setRegionFilter(e.target.value)}
              className="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
            >
              {REGIONS.map((r) => <option key={r} value={r}>{r || 'All regions'}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
            >
              {EVIDENCE_STATUSES.map((s) => <option key={s} value={s}>{s || 'All statuses'}</option>)}
            </select>
          </div>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
        >
          <PlusIcon className="w-4 h-4" />
          Add Source
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          className="bg-white border border-gray-200 rounded-xl p-6 space-y-4"
        >
          <h3 className="text-sm font-semibold text-gray-800">New evidence source</h3>

          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Title <span className="text-red-500">*</span>
              </label>
              <input
                required
                type="text"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="e.g. BNF 2024 Monograph — Metformin"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Organization</label>
              <input
                type="text"
                value={form.organization ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, organization: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="e.g. NICE, BNF, FDA"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Source type</label>
              <input
                type="text"
                value={form.source_type ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, source_type: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="e.g. guideline, monograph, alert"
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-1">URL</label>
              <input
                type="url"
                value={form.url ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="https://…"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Region</label>
              <select
                value={form.region ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, region: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {REGIONS.map((r) => <option key={r} value={r}>{r || 'Not set'}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Status</label>
              <select
                value={form.evidence_status ?? 'active'}
                onChange={(e) => setForm((f) => ({ ...f, evidence_status: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {EVIDENCE_STATUSES.filter(Boolean).map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-1">Notes</label>
              <textarea
                rows={2}
                value={form.notes ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
              />
            </div>
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
              {saving ? 'Saving…' : 'Add Source'}
            </button>
          </div>
        </form>
      )}

      {/* Source list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 animate-pulse rounded-xl" />
          ))}
        </div>
      ) : displaySources.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <BookOpenIcon className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">{showDue ? 'No evidence sources due for review.' : 'No evidence sources found.'}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {displaySources.map((src) => (
            <div key={src.id} className="bg-white border border-gray-200 rounded-xl p-5">
              {editId === src.id ? (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      type="text"
                      value={editForm.title ?? src.title}
                      onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                      className="col-span-2 text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    <select
                      value={editForm.evidence_status ?? src.evidence_status}
                      onChange={(e) => setEditForm((f) => ({ ...f, evidence_status: e.target.value }))}
                      className="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    >
                      {EVIDENCE_STATUSES.filter(Boolean).map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                    <input
                      type="datetime-local"
                      value={editForm.next_review_due_at?.slice(0, 16) ?? ''}
                      onChange={(e) =>
                        setEditForm((f) => ({
                          ...f,
                          next_review_due_at: e.target.value
                            ? new Date(e.target.value).toISOString()
                            : undefined,
                        }))
                      }
                      className="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                      placeholder="Next review due"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleUpdate(src.id)}
                      disabled={saving}
                      className="px-3 py-1.5 text-xs font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
                    >
                      {saving ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      onClick={() => { setEditId(null); setEditForm({}) }}
                      className="px-3 py-1.5 text-xs text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <EvidenceStatusBadge evidenceStatus={src.evidence_status} />
                      {src.region && <RegionBadge region={src.region} />}
                    </div>
                    <p className="font-medium text-gray-900 truncate">{src.title}</p>
                    {src.organization && (
                      <p className="text-xs text-gray-500 mt-0.5">{src.organization}</p>
                    )}
                    {src.url && (
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-xs text-primary-600 hover:underline truncate block max-w-[400px] mt-0.5"
                      >
                        {src.url}
                      </a>
                    )}
                    {src.next_review_due_at && (
                      <p className="text-xs text-amber-600 mt-1">
                        Review due: {new Date(src.next_review_due_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => {
                      setEditId(src.id)
                      setEditForm({ title: src.title, evidence_status: src.evidence_status })
                    }}
                    className="text-xs text-gray-500 hover:text-primary-600 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-primary-50 flex-shrink-0"
                  >
                    Edit
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
