import { useState, useEffect } from 'react'
import {
  CreditCardIcon,
  CheckCircleIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { billingApi } from '@/services/billingApi'
import type { MonthlyUsageResponse, SubscriptionPlanRead, UserSubscriptionWithFallback } from '@/types/billing'

const PLAN_HIGHLIGHT: Record<string, string> = {
  free: 'border-gray-200',
  pro: 'border-primary-400 ring-1 ring-primary-400',
  institution: 'border-teal-400',
  enterprise: 'border-amber-400',
}

const PLAN_BADGE: Record<string, string> = {
  free: 'bg-gray-100 text-gray-600',
  pro: 'bg-primary-100 text-primary-700',
  institution: 'bg-teal-100 text-teal-700',
  enterprise: 'bg-amber-100 text-amber-700',
}

function formatPrice(cents: number, currency: string): string {
  if (cents === 0) return 'Free'
  return `${currency === 'GBP' ? '£' : '$'}${(cents / 100).toFixed(2)}/mo`
}

function PlanCard({
  plan,
  isCurrent,
}: {
  plan: SubscriptionPlanRead
  isCurrent: boolean
}) {
  const [checkoutLoading, setCheckoutLoading] = useState(false)
  const [paypalUnavailable, setPaypalUnavailable] = useState(false)

  const features: string[] = []
  if (plan.max_training_sessions_per_month !== null)
    features.push(`${plan.max_training_sessions_per_month.toLocaleString()} sessions / month`)
  else features.push('Unlimited sessions')
  if (plan.allows_osce) features.push('OSCE stations')
  if (plan.allows_games) features.push('Pharmacy games')
  if (plan.allows_institution_dashboard) features.push('Institution dashboard')
  if (plan.allows_bulk_import) features.push('Bulk content import')
  if (plan.allows_admin_governance) features.push('Admin governance')
  if (!plan.allows_ai_tutor) features.push('AI tutor (coming soon)')

  const handlePayPal = async () => {
    setCheckoutLoading(true)
    setPaypalUnavailable(false)
    try {
      const result = await billingApi.createPayPalCheckout(plan.code)
      window.location.href = result.checkout_url
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 503) {
        setPaypalUnavailable(true)
      } else {
        toast.error('Checkout failed. Please try again.')
      }
    } finally {
      setCheckoutLoading(false)
    }
  }

  const isPaid = plan.price_monthly_cents > 0

  return (
    <div
      className={`relative flex flex-col bg-white border-2 rounded-xl p-6 gap-4 ${PLAN_HIGHLIGHT[plan.code] ?? 'border-gray-200'}`}
    >
      {isCurrent && (
        <span className="absolute top-4 right-4 flex items-center gap-1 text-xs font-semibold text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full">
          <CheckCircleIcon className="w-3.5 h-3.5" /> Current plan
        </span>
      )}
      <div>
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide ${PLAN_BADGE[plan.code] ?? 'bg-gray-100 text-gray-600'}`}>
          {plan.name}
        </span>
        <p className="mt-3 text-2xl font-bold text-gray-900">
          {formatPrice(plan.price_monthly_cents, plan.currency)}
        </p>
      </div>
      <ul className="flex-1 space-y-2">
        {features.map((f) => (
          <li key={f} className="flex items-center gap-2 text-sm text-gray-600">
            <CheckCircleIcon className="w-4 h-4 text-green-500 flex-shrink-0" />
            {f}
          </li>
        ))}
      </ul>
      {!isCurrent && isPaid && (
        <div className="mt-auto pt-2 space-y-2">
          {paypalUnavailable ? (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              PayPal checkout is not configured yet. Contact admin for beta upgrade.
            </p>
          ) : (
            <button
              onClick={handlePayPal}
              disabled={checkoutLoading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-[#0070ba] hover:bg-[#005ea6] disabled:opacity-60 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              {checkoutLoading ? (
                <span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg viewBox="0 0 24 24" className="w-4 h-4 fill-white" xmlns="http://www.w3.org/2000/svg">
                  <path d="M7.076 21.337H2.47a.641.641 0 0 1-.633-.74L4.944.901C5.026.382 5.474 0 5.998 0h7.46c2.57 0 4.578.543 5.69 1.81 1.01 1.15 1.304 2.42 1.012 4.287-.023.143-.047.288-.077.437-.983 5.05-4.349 6.797-8.647 6.797h-2.19c-.524 0-.968.382-1.05.9l-1.12 7.106zm14.146-14.42a3.35 3.35 0 0 0-.607-.541c-.013.076-.026.175-.041.254-.93 4.778-4.005 7.201-9.138 7.201h-2.19a.563.563 0 0 0-.556.479l-1.187 7.527h-.506l-.24 1.516a.56.56 0 0 0 .554.647h3.882c.46 0 .85-.334.922-.788.06-.26.76-4.852.816-5.09a.932.932 0 0 1 .92-.788h.58c3.76 0 6.705-1.528 7.565-5.946.36-1.847.174-3.388-.774-4.471z" />
                </svg>
              )}
              Pay with PayPal
            </button>
          )}
        </div>
      )}
      {!isCurrent && !isPaid && (
        <div className="mt-auto pt-2">
          <p className="text-xs text-gray-400 text-center">No payment required</p>
        </div>
      )}
    </div>
  )
}

export default function BillingPage() {
  const [subInfo, setSubInfo] = useState<UserSubscriptionWithFallback | null>(null)
  const [plans, setPlans] = useState<SubscriptionPlanRead[]>([])
  const [usage, setUsage] = useState<MonthlyUsageResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([billingApi.getMySubscription(), billingApi.getPlans(), billingApi.getMyUsage()])
      .then(([sub, planList, usageData]) => {
        setSubInfo(sub)
        setPlans(planList)
        setUsage(usageData)
      })
      .catch(() => toast.error('Failed to load billing information.'))
      .finally(() => setLoading(false))
  }, [])

  const sessionUsage = usage?.usage.find((u) => u.event_type === 'training_session_started')

  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Subscription & Billing</h1>
        <p className="text-sm text-gray-500 mt-1">
          View your current plan, usage, and available upgrades.
        </p>
      </div>

      {loading ? (
        <div className="space-y-4 animate-pulse">
          <div className="h-24 bg-gray-100 rounded-xl" />
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-48 bg-gray-100 rounded-xl" />
            ))}
          </div>
        </div>
      ) : (
        <>
          {/* Current plan summary */}
          {subInfo && (
            <div className="bg-white border border-gray-200 rounded-xl p-6 flex flex-wrap gap-6 items-center">
              <div className="flex items-center gap-3">
                <CreditCardIcon className="w-8 h-8 text-primary-500" />
                <div>
                  <p className="text-xs text-gray-500">Current plan</p>
                  <p className="text-lg font-bold text-gray-900">{subInfo.plan.name}</p>
                </div>
              </div>

              {subInfo.subscription && (
                <div>
                  <p className="text-xs text-gray-500">Status</p>
                  <p className="text-sm font-semibold capitalize text-gray-800">
                    {subInfo.subscription.status}
                  </p>
                </div>
              )}

              {sessionUsage && (
                <div className="flex items-center gap-4 ml-auto">
                  <ChartBarIcon className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-gray-500">Sessions this month</p>
                    <p className="text-sm font-semibold text-gray-800">
                      {sessionUsage.count.toLocaleString()}
                      {sessionUsage.limit !== null && (
                        <span className="text-gray-400 font-normal">
                          {' '}/ {sessionUsage.limit.toLocaleString()}
                        </span>
                      )}
                    </p>
                  </div>
                  {sessionUsage.limit !== null && (
                    <div className="w-32 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary-500 rounded-full"
                        style={{
                          width: `${Math.min(100, (sessionUsage.count / sessionUsage.limit) * 100)}%`,
                        }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Plan cards */}
          <div>
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Available plans</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {plans.map((plan) => (
                <PlanCard
                  key={plan.id}
                  plan={plan}
                  isCurrent={subInfo?.plan.code === plan.code}
                />
              ))}
            </div>
          </div>

          {/* Upgrade note */}
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
            <p className="font-semibold mb-1">PayPal checkout (beta)</p>
            <p>
              Subscriptions are activated automatically after PayPal payment is confirmed. If you
              experience any issues, contact your platform administrator.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
