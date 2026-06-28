import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  UserCircleIcon,
  PencilSquareIcon,
  CheckIcon,
  XMarkIcon,
  ArrowRightStartOnRectangleIcon,
  CreditCardIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { authApi } from '@/services/api'
import { billingApi } from '@/services/billingApi'
import { useAppStore } from '@/store/appStore'
import type { SubscriptionPlanRead } from '@/types/billing'

const PLAN_BADGE: Record<string, string> = {
  free: 'bg-gray-100 text-gray-600',
  pro: 'bg-primary-100 text-primary-700',
  institution: 'bg-teal-100 text-teal-700',
  enterprise: 'bg-amber-100 text-amber-700',
}

export default function ProfilePage() {
  const navigate = useNavigate()
  const { currentUser, setCurrentUser } = useAppStore()

  const [editing, setEditing] = useState(false)
  const [fullName, setFullName] = useState(currentUser?.full_name ?? '')
  const [username, setUsername] = useState(currentUser?.username ?? '')
  const [saving, setSaving] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<{ username?: string }>({})
  const [plan, setPlan] = useState<SubscriptionPlanRead | null>(null)

  useEffect(() => {
    billingApi
      .getMySubscription()
      .then((sub) => setPlan(sub.plan))
      .catch(() => {})
  }, [])

  if (!currentUser) return null

  const handleEdit = () => {
    setFullName(currentUser.full_name ?? '')
    setUsername(currentUser.username)
    setFieldErrors({})
    setEditing(true)
  }

  const handleCancel = () => {
    setEditing(false)
    setFieldErrors({})
  }

  const handleSave = async () => {
    const errors: { username?: string } = {}
    if (username.length < 3) errors.username = 'At least 3 characters.'
    if (!/^[a-zA-Z0-9_-]+$/.test(username)) errors.username = 'Letters, digits, _ and - only.'
    if (Object.keys(errors).length > 0) { setFieldErrors(errors); return }

    setSaving(true)
    try {
      const updated = await authApi.updateMe({
        full_name: fullName.trim() || null,
        username: username.trim(),
      })
      setCurrentUser(updated)
      setEditing(false)
      toast.success('Profile updated.')
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : 'Failed to update profile.'
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleLogout = async () => {
    await authApi.logout()
    toast.success('Signed out.')
    navigate('/login', { replace: true })
  }

  const displayName = currentUser.full_name || currentUser.username

  return (
    <div className="max-w-xl">
      <div className="flex items-center gap-3 mb-6">
        <UserCircleIcon className="w-7 h-7 text-primary-600" />
        <h1 className="text-xl font-semibold text-gray-900">My Profile</h1>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {/* Avatar / header */}
        <div className="bg-gradient-to-r from-primary-600 to-primary-500 px-6 py-8 flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-white text-primary-700 flex items-center justify-center text-xl font-bold flex-shrink-0">
            {displayName.slice(0, 2).toUpperCase()}
          </div>
          <div>
            <p className="text-lg font-semibold text-white">{displayName}</p>
            <p className="text-primary-200 text-sm">{currentUser.email}</p>
            {currentUser.is_superuser && (
              <span className="inline-block mt-1 px-2 py-0.5 bg-amber-400 text-amber-900 text-xs font-semibold rounded-full">
                Administrator
              </span>
            )}
            {plan && (
              <Link
                to="/billing"
                className={`inline-flex items-center gap-1 mt-1 ml-1 px-2 py-0.5 text-xs font-semibold rounded-full ${PLAN_BADGE[plan.code] ?? 'bg-gray-100 text-gray-600'}`}
              >
                <CreditCardIcon className="w-3 h-3" />
                {plan.name}
              </Link>
            )}
          </div>
        </div>

        {/* Details */}
        <div className="px-6 py-6 space-y-4">
          {editing ? (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Full name</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Jane Smith"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => { setUsername(e.target.value); setFieldErrors({}) }}
                  className={`w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 ${fieldErrors.username ? 'border-red-400' : 'border-gray-300'}`}
                />
                {fieldErrors.username && (
                  <p className="mt-1 text-xs text-red-500">{fieldErrors.username}</p>
                )}
              </div>
              <div className="flex gap-2 pt-1">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-1.5 px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-lg hover:bg-primary-700 disabled:opacity-50 transition-colors"
                >
                  <CheckIcon className="w-4 h-4" />
                  {saving ? 'Saving…' : 'Save'}
                </button>
                <button
                  onClick={handleCancel}
                  disabled={saving}
                  className="flex items-center gap-1.5 px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <XMarkIcon className="w-4 h-4" />
                  Cancel
                </button>
              </div>
            </>
          ) : (
            <>
              <dl className="space-y-3">
                <div className="flex justify-between text-sm">
                  <dt className="text-gray-500">Full name</dt>
                  <dd className="text-gray-900 font-medium">{currentUser.full_name || <span className="text-gray-400 font-normal">—</span>}</dd>
                </div>
                <div className="flex justify-between text-sm">
                  <dt className="text-gray-500">Username</dt>
                  <dd className="text-gray-900 font-medium">{currentUser.username}</dd>
                </div>
                <div className="flex justify-between text-sm">
                  <dt className="text-gray-500">Email</dt>
                  <dd className="text-gray-900 font-medium">{currentUser.email}</dd>
                </div>
                <div className="flex justify-between text-sm">
                  <dt className="text-gray-500">Account status</dt>
                  <dd>
                    {currentUser.is_active
                      ? <span className="text-green-700 font-medium">Active</span>
                      : <span className="text-red-600 font-medium">Inactive</span>}
                  </dd>
                </div>
                <div className="flex justify-between text-sm">
                  <dt className="text-gray-500">Member since</dt>
                  <dd className="text-gray-900 font-medium">
                    {new Date(currentUser.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
                  </dd>
                </div>
              </dl>

              <div className="pt-2 flex gap-2">
                <button
                  onClick={handleEdit}
                  className="flex items-center gap-1.5 px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <PencilSquareIcon className="w-4 h-4" />
                  Edit profile
                </button>
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-1.5 px-4 py-2 border border-red-200 text-red-600 text-sm font-medium rounded-lg hover:bg-red-50 transition-colors"
                >
                  <ArrowRightStartOnRectangleIcon className="w-4 h-4" />
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
