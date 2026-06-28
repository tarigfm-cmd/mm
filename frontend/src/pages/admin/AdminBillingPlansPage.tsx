import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { billingApi } from '@/services/billingApi'
import type { SubscriptionPlanAdminRead, SubscriptionPlanUpdate } from '@/types/billing'

function formatCents(cents: number): string {
  if (cents === 0) return 'Free'
  return `$${(cents / 100).toFixed(2)}/mo`
}

interface EditModalProps {
  plan: SubscriptionPlanAdminRead
  onClose: () => void
  onSaved: (updated: SubscriptionPlanAdminRead) => void
}

function EditModal({ plan, onClose, onSaved }: EditModalProps) {
  const [paypalId, setPaypalId] = useState(plan.external_paypal_plan_id ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isFree = plan.price_monthly_cents === 0

  async function handleSave() {
    setSaving(true)
    setError(null)
    const updates: SubscriptionPlanUpdate = {
      external_paypal_plan_id: paypalId.trim() === '' ? null : paypalId.trim(),
    }
    try {
      const updated = await billingApi.adminUpdatePlan(plan.code, updates)
      toast.success(`Plan "${plan.name}" updated.`)
      onSaved(updated)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Save failed. Check the PayPal Plan ID and try again.'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">
          Edit Plan — {plan.name}
        </h2>
        <p className="text-sm text-gray-500 mb-5">
          Code: <code className="bg-gray-100 px-1 rounded">{plan.code}</code>
          {' · '}
          {formatCents(plan.price_monthly_cents)}
          {' · '}
          {plan.is_active ? 'Active' : 'Inactive'}
        </p>

        <label className="block text-sm font-medium text-gray-700 mb-1">
          PayPal Plan ID
        </label>
        {isFree ? (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
            Free plans cannot have a PayPal Plan ID.
          </p>
        ) : (
          <>
            <input
              type="text"
              value={paypalId}
              onChange={(e) => setPaypalId(e.target.value)}
              placeholder="P-XXXXXXXXXXXXXXXXXXXXXXXX"
              className="block w-full rounded border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              Paste the PayPal Billing Plan ID from the PayPal Developer Dashboard.
              Leave blank to remove the current value.
            </p>
          </>
        )}

        {error && (
          <p className="mt-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
            {error}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          {!isFree && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function AdminBillingPlansPage() {
  const [plans, setPlans] = useState<SubscriptionPlanAdminRead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<SubscriptionPlanAdminRead | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    billingApi.adminListPlans()
      .then((data) => { if (!cancelled) setPlans(data) })
      .catch(() => { if (!cancelled) setError('Failed to load plans.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  function handleSaved(updated: SubscriptionPlanAdminRead) {
    setPlans((prev) => prev.map((p) => (p.code === updated.code ? updated : p)))
    setEditing(null)
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Subscription Plan Configuration</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage PayPal Plan IDs for each subscription tier. Only superusers can access this page.
        </p>
      </div>

      {loading && (
        <p className="text-sm text-gray-500">Loading plans…</p>
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">
          {error}
        </p>
      )}

      {!loading && !error && (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Plan</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Code</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Price</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">PayPal Plan ID</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {plans.map((plan) => (
                <tr key={plan.code} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{plan.name}</td>
                  <td className="px-4 py-3 font-mono text-gray-600">{plan.code}</td>
                  <td className="px-4 py-3 text-gray-600">{formatCents(plan.price_monthly_cents)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        plan.is_active
                          ? 'inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800'
                          : 'inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600'
                      }
                    >
                      {plan.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500 max-w-xs truncate">
                    {plan.external_paypal_plan_id ?? (
                      <span className="text-amber-600 font-sans not-italic">Not set</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setEditing(plan)}
                      className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <EditModal
          plan={editing}
          onClose={() => setEditing(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
