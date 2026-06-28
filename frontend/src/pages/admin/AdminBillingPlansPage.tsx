import { useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  ClipboardDocumentIcon,
} from '@heroicons/react/24/outline'
import { billingApi } from '@/services/billingApi'
import type {
  PayPalConfigStatus,
  SubscriptionPlanAdminRead,
  SubscriptionPlanUpdate,
} from '@/types/billing'

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatCents(cents: number): string {
  if (cents === 0) return 'Free'
  return `$${(cents / 100).toFixed(2)}/mo`
}

function copyToClipboard(text: string, label: string) {
  navigator.clipboard.writeText(text).then(
    () => toast.success(`${label} copied to clipboard.`),
    () => toast.error('Copy failed — select the text manually.'),
  )
}

// ── PayPal Readiness Panel ────────────────────────────────────────────────

interface StatusRowProps {
  label: string
  ok: boolean
  okText?: string
  failText?: string
}

function StatusRow({ label, ok, okText = 'Configured', failText = 'Not set' }: StatusRowProps) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-gray-600">{label}</span>
      {ok ? (
        <span className="inline-flex items-center gap-1 text-green-700 font-medium">
          <CheckCircleIcon className="w-4 h-4" /> {okText}
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 text-red-600 font-medium">
          <XCircleIcon className="w-4 h-4" /> {failText}
        </span>
      )}
    </div>
  )
}

interface CopyUrlRowProps {
  label: string
  url: string
}

function CopyUrlRow({ label, url }: CopyUrlRowProps) {
  return (
    <div className="flex items-center gap-2 py-1.5">
      <span className="text-sm text-gray-600 w-28 shrink-0">{label}</span>
      <code className="flex-1 text-xs bg-gray-50 border border-gray-200 rounded px-2 py-1 truncate">
        {url}
      </code>
      <button
        onClick={() => copyToClipboard(url, label)}
        title={`Copy ${label}`}
        className="p-1 text-gray-400 hover:text-gray-700 rounded transition-colors"
      >
        <ClipboardDocumentIcon className="w-4 h-4" />
      </button>
    </div>
  )
}

function PayPalReadinessPanel({ status }: { status: PayPalConfigStatus }) {
  const envLabel =
    status.paypal_env === 'live'
      ? 'Live (production)'
      : status.paypal_env === 'sandbox'
      ? 'Sandbox (test)'
      : status.paypal_env

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-sm mb-6">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-base font-semibold text-gray-900">PayPal Configuration Status</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Local readiness check — credential presence only. No live API call is made.
        </p>
      </div>

      <div className="px-5 py-4 grid grid-cols-1 md:grid-cols-2 gap-x-10 gap-y-0">
        {/* Left: credentials */}
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Credentials
          </p>
          <div className="text-sm text-gray-600 mb-2">
            Environment:{' '}
            <span className={`font-semibold ${status.paypal_env === 'live' ? 'text-amber-700' : 'text-gray-800'}`}>
              {envLabel}
            </span>
          </div>
          <StatusRow label="Client ID" ok={status.client_id_configured} />
          <StatusRow label="Client Secret" ok={status.client_secret_configured} />
          <StatusRow
            label="Webhook ID"
            ok={status.webhook_id_configured}
            failText="Not set — webhooks rejected"
          />
        </div>

        {/* Right: URLs */}
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            URLs
          </p>
          <CopyUrlRow label="Webhook URL" url={status.webhook_url} />
          <CopyUrlRow label="Success URL" url={status.success_url} />
          <CopyUrlRow label="Cancel URL" url={status.cancel_url} />
          <p className="text-xs text-gray-400 mt-1">
            Set the Webhook URL in the PayPal Developer Dashboard to receive events.
          </p>
        </div>
      </div>

      {/* Missing requirements */}
      {status.missing_requirements.length > 0 && (
        <div className="mx-5 mb-4 bg-red-50 border border-red-200 rounded p-3">
          <p className="text-xs font-semibold text-red-700 mb-1 flex items-center gap-1">
            <XCircleIcon className="w-3.5 h-3.5" /> Missing requirements
          </p>
          <ul className="space-y-0.5">
            {status.missing_requirements.map((req) => (
              <li key={req} className="text-xs text-red-700">
                • {req}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings */}
      {status.warnings.length > 0 && (
        <div className="mx-5 mb-4 bg-amber-50 border border-amber-200 rounded p-3">
          <p className="text-xs font-semibold text-amber-700 mb-1 flex items-center gap-1">
            <ExclamationTriangleIcon className="w-3.5 h-3.5" /> Warnings
          </p>
          <ul className="space-y-0.5">
            {status.warnings.map((w) => (
              <li key={w} className="text-xs text-amber-700">
                • {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* All good */}
      {status.missing_requirements.length === 0 && status.warnings.length === 0 && (
        <div className="mx-5 mb-4 bg-green-50 border border-green-200 rounded p-3 flex items-center gap-2">
          <CheckCircleIcon className="w-4 h-4 text-green-600 shrink-0" />
          <p className="text-xs text-green-700 font-medium">
            All PayPal credentials are configured and webhook verification is enabled.
          </p>
        </div>
      )}
    </div>
  )
}

// ── Edit Modal ────────────────────────────────────────────────────────────

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

// ── Checkout readiness badge ──────────────────────────────────────────────

function CheckoutBadge({ ready, isPaid }: { ready: boolean; isPaid: boolean }) {
  if (!isPaid) {
    return (
      <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
        N/A
      </span>
    )
  }
  return ready ? (
    <span className="inline-flex items-center gap-0.5 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
      <CheckCircleIcon className="w-3 h-3" /> Ready
    </span>
  ) : (
    <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
      <ExclamationTriangleIcon className="w-3 h-3" /> Not ready
    </span>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────

export default function AdminBillingPlansPage() {
  const [plans, setPlans] = useState<SubscriptionPlanAdminRead[]>([])
  const [paypalStatus, setPaypalStatus] = useState<PayPalConfigStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<SubscriptionPlanAdminRead | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const [planData, statusData] = await Promise.all([
        billingApi.adminListPlans(),
        billingApi.adminGetPayPalStatus(),
      ])
      setPlans(planData)
      setPaypalStatus(statusData)
    } catch {
      setError('Failed to load plan configuration.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    load().catch(() => { if (!cancelled) setError('Failed to load plan configuration.') })
    return () => { cancelled = true }
  }, [])

  function handleSaved(updated: SubscriptionPlanAdminRead) {
    setPlans((prev) => prev.map((p) => (p.code === updated.code ? updated : p)))
    setEditing(null)
    // Re-fetch PayPal status to reflect new checkout_ready values
    billingApi.adminGetPayPalStatus().then(setPaypalStatus).catch(() => undefined)
  }

  const checkoutReadyByCode = Object.fromEntries(
    (paypalStatus?.plans ?? []).map((p) => [p.plan_code, p.checkout_ready]),
  )
  const isPaidByCode = Object.fromEntries(
    (paypalStatus?.plans ?? []).map((p) => [p.plan_code, p.is_paid]),
  )

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Subscription Plan Configuration</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage PayPal Plan IDs and review configuration readiness. Superusers only.
        </p>
      </div>

      {loading && (
        <p className="text-sm text-gray-500">Loading…</p>
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-4 py-3">
          {error}
        </p>
      )}

      {!loading && !error && (
        <>
          {paypalStatus && <PayPalReadinessPanel status={paypalStatus} />}

          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Plan</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Code</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Price</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">PayPal Plan ID</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Checkout</th>
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
                    <td className="px-4 py-3">
                      <CheckoutBadge
                        ready={checkoutReadyByCode[plan.code] ?? false}
                        isPaid={isPaidByCode[plan.code] ?? false}
                      />
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
        </>
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
