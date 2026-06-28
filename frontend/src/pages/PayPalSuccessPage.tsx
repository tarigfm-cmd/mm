import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import { billingApi } from '@/services/billingApi'
import type { UserSubscriptionWithFallback } from '@/types/billing'

export default function PayPalSuccessPage() {
  const [subInfo, setSubInfo] = useState<UserSubscriptionWithFallback | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    billingApi.getMySubscription()
      .then(setSubInfo)
      .catch(() => null)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center space-y-6">
        <div className="flex justify-center">
          <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center">
            <CheckCircleIcon className="w-9 h-9 text-green-500" />
          </div>
        </div>

        <div>
          <h1 className="text-2xl font-bold text-gray-900">Payment received</h1>
          <p className="mt-2 text-sm text-gray-600">
            PayPal has received your payment. Your subscription will activate automatically
            once PayPal sends the confirmation — this usually takes a few seconds.
          </p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-2 text-sm text-gray-400">
            <ArrowPathIcon className="w-4 h-4 animate-spin" />
            Checking subscription status…
          </div>
        ) : subInfo && subInfo.subscription?.status === 'active' ? (
          <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-800">
            Your <strong>{subInfo.plan.name}</strong> subscription is now active.
          </div>
        ) : (
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
            Activation is pending PayPal confirmation. If your plan does not update within
            a few minutes, contact your platform administrator.
          </div>
        )}

        <div className="flex flex-col gap-2">
          <Link
            to="/billing"
            className="w-full inline-flex items-center justify-center px-4 py-2.5 text-sm font-semibold text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
          >
            View my subscription
          </Link>
          <Link
            to="/learn/content"
            className="w-full inline-flex items-center justify-center px-4 py-2.5 text-sm font-medium text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg transition-colors"
          >
            Go to training library
          </Link>
        </div>
      </div>
    </div>
  )
}
