import { Link } from 'react-router-dom'
import { XCircleIcon } from '@heroicons/react/24/outline'

export default function PayPalCancelPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center space-y-6">
        <div className="flex justify-center">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
            <XCircleIcon className="w-9 h-9 text-gray-400" />
          </div>
        </div>

        <div>
          <h1 className="text-2xl font-bold text-gray-900">Checkout cancelled</h1>
          <p className="mt-2 text-sm text-gray-600">
            Your PayPal checkout was cancelled. No payment has been taken and your
            current plan has not changed.
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <Link
            to="/billing"
            className="w-full inline-flex items-center justify-center px-4 py-2.5 text-sm font-semibold text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors"
          >
            Back to billing
          </Link>
          <Link
            to="/learn/content"
            className="w-full inline-flex items-center justify-center px-4 py-2.5 text-sm font-medium text-gray-600 hover:text-gray-900 border border-gray-200 rounded-lg transition-colors"
          >
            Continue with free plan
          </Link>
        </div>
      </div>
    </div>
  )
}
