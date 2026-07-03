import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { PlusIcon, MapPinIcon } from '@heroicons/react/24/outline'
import { regionRulesApi } from '@/services/governanceApi'
import RegionBadge from '@/components/governance/RegionBadge'
import ConfirmActionDialog from '@/components/governance/ConfirmActionDialog'
import type { RegionPublishingRuleRead, RegionPublishingRuleCreate, RegionPublishingRuleUpdate } from '@/types/governance'

const REGION_CODES = ['UK', 'US', 'GCC', 'AU']
const CONTENT_TYPES = [
  '', 'case', 'simulation', 'osce_station', 'prescription_screening',
  'drill', 'game', 'evidence_source', 'taxonomy_node',
]
const CONTENT_STATUSES = [
  'draft', 'imported', 'pending_review', 'clinically_approved',
  'published', 'unpublished', 'needs_update', 'retired',
]

const EMPTY_FORM: RegionPublishingRuleCreate = {
  region_code: 'UK',
  content_type: undefined,
  allowed_statuses: undefined,
  is_active: true,
}

export default function RegionRulesPage() {
  const [rules, setRules] = useState<RegionPublishingRuleRead[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<RegionPublishingRuleCreate>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<RegionPublishingRuleUpdate>({})
  const [confirmDeactivate, setConfirmDeactivate] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const data = await regionRulesApi.list()
      setRules(data)
    } catch {
      toast.error('Failed to load region rules.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload: RegionPublishingRuleCreate = {
        ...form,
        content_type: form.content_type || undefined,
        allowed_statuses: form.allowed_statuses?.length ? form.allowed_statuses : undefined,
      }
      const created = await regionRulesApi.create(payload)
      setRules((prev) => [...prev, created])
      toast.success('Region rule created.')
      setShowForm(false)
      setForm(EMPTY_FORM)
    } catch {
      toast.error('Failed to create region rule. Check field values.')
    } finally {
      setSaving(false)
    }
  }

  const handleUpdate = async (id: string) => {
    setSaving(true)
    try {
      const updated = await regionRulesApi.update(id, editForm)
      setRules((prev) => prev.map((r) => (r.id === id ? updated : r)))
      toast.success('Region rule updated.')
      setEditId(null)
      setEditForm({})
    } catch {
      toast.error('Failed to update region rule.')
    } finally {
      setSaving(false)
    }
  }

  const handleDeactivateConfirmed = async () => {
    if (!confirmDeactivate) return
    setSaving(true)
    try {
      const updated = await regionRulesApi.update(confirmDeactivate, { is_active: false })
      setRules((prev) => prev.map((r) => (r.id === confirmDeactivate ? updated : r)))
      toast.success('Region rule deactivated.')
    } catch {
      toast.error('Failed to deactivate rule.')
    } finally {
      setSaving(false)
      setConfirmDeactivate(null)
    }
  }

  const toggleAllowedStatus = (status: string) => {
    setForm((f) => {
      const current = f.allowed_statuses ?? []
      return {
        ...f,
        allowed_statuses: current.includes(status)
          ? current.filter((s) => s !== status)
          : [...current, status],
      }
    })
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-700">
        <MapPinIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold">Region publishing rules</p>
          <p className="mt-1 text-xs text-blue-600">
            Rules gate what content can be published in each region. A rule is applied at publish time
            if it matches the item's region code and content type. Requires <span className="font-mono">content.publish</span>{' '}
            permission to create or update rules.
          </p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowForm((s) => !s)}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
        >
          <PlusIcon className="w-4 h-4" />
          Add Rule
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form
          onSubmit={handleCreate}
          className="bg-white border border-gray-200 rounded-xl p-6 space-y-4"
        >
          <h3 className="text-sm font-semibold text-gray-800">New region publishing rule</h3>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                Region <span className="text-red-500">*</span>
              </label>
              <select
                value={form.region_code}
                onChange={(e) => setForm((f) => ({ ...f, region_code: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {REGION_CODES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Content type (optional)</label>
              <select
                value={form.content_type ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, content_type: e.target.value || undefined }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                {CONTENT_TYPES.map((t) => <option key={t} value={t}>{t || 'Any type'}</option>)}
              </select>
            </div>

            <div className="col-span-2">
              <label className="block text-xs font-medium text-gray-500 mb-2">
                Allowed statuses (if blank, no status restriction)
              </label>
              <div className="flex flex-wrap gap-2">
                {CONTENT_STATUSES.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleAllowedStatus(s)}
                    className={`px-2.5 py-1 text-xs font-medium rounded-full border transition-colors ${
                      (form.allowed_statuses ?? []).includes(s)
                        ? 'bg-primary-600 text-white border-primary-600'
                        : 'bg-white text-gray-600 border-gray-300 hover:border-primary-400'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Required evidence region</label>
              <input
                type="text"
                value={form.required_evidence_region ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, required_evidence_region: e.target.value || undefined }))}
                placeholder="e.g. UK"
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            <div className="flex flex-col gap-2 justify-end">
              <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.requires_local_disclaimer ?? false}
                  onChange={(e) => setForm((f) => ({ ...f, requires_local_disclaimer: e.target.checked }))}
                  className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                Requires local disclaimer
              </label>
              <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.requires_protocol_note ?? false}
                  onChange={(e) => setForm((f) => ({ ...f, requires_protocol_note: e.target.checked }))}
                  className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                Requires protocol note
              </label>
              <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_active ?? true}
                  onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                  className="w-4 h-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                />
                Active (enforced at publish time)
              </label>
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
              {saving ? 'Saving…' : 'Add Rule'}
            </button>
          </div>
        </form>
      )}

      {/* Rules list */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-gray-100 animate-pulse rounded-xl" />)}
        </div>
      ) : rules.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <MapPinIcon className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="text-sm">No region rules defined yet.</p>
          <p className="text-xs mt-1 text-gray-400">
            Rules are seeded automatically during import. Add custom rules above if needed.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={`bg-white border rounded-xl p-5 ${
                rule.is_active ? 'border-gray-200' : 'border-gray-100 opacity-60'
              }`}
            >
              {editId === rule.id ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2 items-center">
                    <RegionBadge region={rule.region_code} />
                    <span className="text-xs text-gray-400">{rule.content_type ?? 'all types'}</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {CONTENT_STATUSES.map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() =>
                          setEditForm((f) => {
                            const current = f.allowed_statuses ?? rule.allowed_statuses ?? []
                            return {
                              ...f,
                              allowed_statuses: current.includes(s)
                                ? current.filter((x) => x !== s)
                                : [...current, s],
                            }
                          })
                        }
                        className={`px-2.5 py-1 text-xs font-medium rounded-full border transition-colors ${
                          (editForm.allowed_statuses ?? rule.allowed_statuses ?? []).includes(s)
                            ? 'bg-primary-600 text-white border-primary-600'
                            : 'bg-white text-gray-600 border-gray-300 hover:border-primary-400'
                        }`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                  <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editForm.is_active ?? rule.is_active}
                      onChange={(e) => setEditForm((f) => ({ ...f, is_active: e.target.checked }))}
                      className="w-4 h-4 rounded border-gray-300"
                    />
                    Active
                  </label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleUpdate(rule.id)}
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
                  <div className="flex-1 space-y-1.5">
                    <div className="flex items-center gap-2">
                      <RegionBadge region={rule.region_code} />
                      {rule.content_type && (
                        <span className="text-xs font-mono text-gray-500">{rule.content_type}</span>
                      )}
                      {!rule.is_active && (
                        <span className="text-xs text-gray-400 border border-gray-200 rounded px-1.5 py-0.5">
                          inactive
                        </span>
                      )}
                    </div>
                    {rule.allowed_statuses && rule.allowed_statuses.length > 0 && (
                      <p className="text-xs text-gray-500">
                        Allowed: {rule.allowed_statuses.join(', ')}
                      </p>
                    )}
                    {rule.required_evidence_region && (
                      <p className="text-xs text-gray-500">
                        Requires evidence region: <span className="font-mono">{rule.required_evidence_region}</span>
                      </p>
                    )}
                    {(rule.requires_local_disclaimer || rule.requires_protocol_note) && (
                      <p className="text-xs text-amber-600">
                        {[
                          rule.requires_local_disclaimer && 'local disclaimer',
                          rule.requires_protocol_note && 'protocol note',
                        ].filter(Boolean).join(' · ')} required
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <button
                      onClick={() => { setEditId(rule.id); setEditForm({}) }}
                      className="text-xs text-gray-500 hover:text-primary-600 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-primary-50"
                    >
                      Edit
                    </button>
                    {rule.is_active && (
                      <button
                        onClick={() => setConfirmDeactivate(rule.id)}
                        className="text-xs text-gray-500 hover:text-red-600 border border-gray-200 rounded-lg px-3 py-1.5 hover:bg-red-50"
                      >
                        Deactivate
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-500 space-y-1">
        <p className="font-medium text-gray-600">How region rules are enforced</p>
        <ul className="list-disc list-inside space-y-0.5 mt-1">
          <li>At publish time the backend checks for any active rule matching the item's region code and content type.</li>
          <li>If <span className="font-mono">allowed_statuses</span> is set, the item's current status must be in that list.</li>
          <li>If <span className="font-mono">required_evidence_region</span> is set, at least one active evidence source from that region must exist.</li>
          <li>Inactive rules (deactivated) are skipped — useful for drafting rules before enforcement.</li>
          <li>Rules do not affect unpublish or rollback operations.</li>
        </ul>
      </div>

      <ConfirmActionDialog
        open={!!confirmDeactivate}
        title="Deactivate this region rule?"
        description={
          <div>
            <p>This rule will no longer be enforced at publish time.</p>
            <p className="mt-1 text-gray-500">You can re-activate it by editing the rule.</p>
          </div>
        }
        confirmLabel="Deactivate"
        confirmVariant="warning"
        loading={saving}
        onConfirm={handleDeactivateConfirmed}
        onCancel={() => setConfirmDeactivate(null)}
      />
    </div>
  )
}
