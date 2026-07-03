import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowPathIcon, CheckCircleIcon, ClockIcon } from '@heroicons/react/24/outline'
import { billingApi } from '@/services/billingApi'
import type { UserSubscriptionWithFallback } from '@/types/billing'

const POLL_INTERVAL_MS = 4000
const MAX_POLLS = 8

export default function PayPalSuccessPage() {
  const [subInfo, setSubInfo] = useState<UserSubscriptionWithFallback | null>(null)
  const [loading, setLoading] = useState(true)
  const [polling, setPolling] = useState(false)
  const pollCount = useRef(0)

  const checkStatus = async () => {
    try {
      const info = await billingApi.getMySubscription()
      setSubInfo(info)
      return info
    } catch {
      return null
    }
  }

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>

    const poll = async () => {
      const info = await checkStatus()
      setLoading(false)

      const isActive = info?.subscription?.status === 'active'
      if (!isActive && pollCount.current < MAX_POLLS) {
        pollCount.current += 1
        setPolling(true)
        timer = setTimeout(poll, POLL_INTERVAL_MS)
      } else {
        setPolling(false)
      }
    }

    poll()
    return () => clearTimeout(timer)
  }, [])

  const handleRefresh = async () => {
    setLoading(true)
    await checkStatus()
    setLoading(false)
  }

  const isActive = subInfo?.subscription?.status === 'active'

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center space-y-6">
        <div className="flex justify-center">
          <div className={`w-16 h-16 rounded-full flex items-center justify-center ${isActive ? 'bg-green-50' : 'bg-amber-50'}`}>
            {isActive
              ? <CheckCircleIcon className="w-9 h-9 text-green-500" />
              : <ClockIcon className="w-9 h-9 text-amber-500" />
            }
          </div>
        </div>

        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {isActive ? 'Subscription activated' : 'PayPal checkout completed'}
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            {isActive
              ? `Your ${subInfo?.plan.name} subscription is now active.`
              : 'Your subscription will activate automatically once PayPal confirms the payment. This usually takes a few seconds.'}
          </p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-2 text-sm text-gray-400">
            <ArrowPathIcon className="w-4 h-4 animate-spin" />
            Checking subscription status…
          </div>
        ) : !isActive ? (
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800 space-y-2">
            <p>
              {polling
                ? 'Waiting for PayPal confirmation…'
                : 'Activation depends on PayPal webhook confirmation. If your plan does not update within a few minutes, contact your platform administrator.'}
            </p>
            {polling && (
              <div className="flex items-center justify-center gap-1.5 text-amber-600">
                <ArrowPathIcon className="w-3.5 h-3.5 animate-spin" />
                <span className="text-xs">Checking again shortly…</span>
              </div>
            )}
            {!polling && (
              <button
                onClick={handleRefresh}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700 hover:text-amber-900 underline"
              >
                <ArrowPathIcon className="w-3.5 h-3.5" />
                Check again
              </button>
            )}
          </div>
        ) : (
          <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm text-green-800">
            You now have access to all <strong>{subInfo?.plan.name}</strong> features.
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
