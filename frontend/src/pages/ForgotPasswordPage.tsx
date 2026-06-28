import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AcademicCapIcon, ExclamationCircleIcon, CheckCircleIcon } from '@heroicons/react/24/outline'
import { authApi } from '@/services/api'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [resetUrl, setResetUrl] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return

    setError(null)
    setLoading(true)
    try {
      const result = await authApi.forgotPassword({ email: email.trim() })
      setResetUrl(result.reset_url ?? null)
      setSubmitted(true)
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary-700 via-primary-600 to-primary-500 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 bg-white rounded-2xl flex items-center justify-center shadow-lg mb-3">
            <AcademicCapIcon className="w-8 h-8 text-primary-600" />
          </div>
          <h1 className="text-2xl font-bold text-white">PharmLearn AI</h1>
          <p className="text-primary-200 text-sm mt-1">Clinical Training Platform</p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-8">
          {submitted ? (
            <div className="text-center">
              <CheckCircleIcon className="w-12 h-12 text-green-500 mx-auto mb-3" />
              <h2 className="text-xl font-semibold text-gray-900 mb-2">Check your email</h2>
              <p className="text-sm text-gray-500 mb-4">
                If an account exists with that email, password reset instructions have been sent.
              </p>

              {resetUrl && (
                <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-left">
                  <p className="text-xs font-semibold text-amber-800 mb-1">Dev mode — reset link:</p>
                  <a
                    href={resetUrl}
                    className="text-xs text-primary-600 break-all hover:underline"
                  >
                    {resetUrl}
                  </a>
                </div>
              )}

              <Link
                to="/login"
                className="inline-block w-full py-2.5 bg-primary-600 text-white font-medium text-sm rounded-lg hover:bg-primary-700 transition-colors text-center"
              >
                Back to sign in
              </Link>
            </div>
          ) : (
            <>
              <h2 className="text-xl font-semibold text-gray-900 mb-1">Forgot password?</h2>
              <p className="text-sm text-gray-500 mb-6">
                Enter your email and we'll send reset instructions.
              </p>

              {error && (
                <div className="mb-4 flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Email address
                  </label>
                  <input
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setError(null) }}
                    placeholder="you@example.com"
                    className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || !email.trim()}
                  className="w-full py-2.5 bg-primary-600 text-white font-medium text-sm rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  {loading ? 'Sending…' : 'Send reset link'}
                </button>
              </form>

              <p className="mt-5 text-center text-sm text-gray-500">
                Remember your password?{' '}
                <Link to="/login" className="text-primary-600 font-medium hover:text-primary-700">
                  Sign in
                </Link>
              </p>
            </>
          )}
        </div>

        <p className="text-center text-xs text-primary-300 mt-6">
          Powered by Claude AI · For educational use only
        </p>
      </div>
    </div>
  )
}
