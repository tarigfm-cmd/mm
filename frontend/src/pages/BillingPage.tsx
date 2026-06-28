import { useState, useEffect } from 'react'
import {
  CreditCardIcon,
  CheckCircleIcon,
  ChartBarIcon,
  SparklesIcon,
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
      {!isCurrent && (
        <div className="mt-auto pt-2">
          <div className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-gray-500 bg-gray-50 border border-gray-200 rounded-lg cursor-not-allowed">
            <SparklesIcon className="w-4 h-4" />
            Online checkout coming soon
          </div>
          <p className="text-xs text-gray-400 text-center mt-1.5">
            Contact your admin to upgrade during beta.
          </p>
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
            <p className="font-semibold mb-1">Upgrading during beta</p>
            <p>
              Online checkout is coming soon. During beta, contact your platform administrator to
              manually upgrade your subscription.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
