import { Navigate, Outlet } from 'react-router-dom'
import { useAppStore } from '@/store/appStore'
import LoadingSpinner from '@/components/LoadingSpinner'
import { ShieldExclamationIcon } from '@heroicons/react/24/outline'

export default function AdminRoute() {
  const { currentUser, authInitialized } = useAppStore()

  if (!authInitialized) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" label="Loading…" />
      </div>
    )
  }

  if (!currentUser) {
    return <Navigate to="/login" replace />
  }

  if (!currentUser.is_superuser) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4 text-center">
        <ShieldExclamationIcon className="w-12 h-12 text-amber-400" />
        <h2 className="text-xl font-semibold text-gray-800">Insufficient permissions</h2>
        <p className="text-sm text-gray-500 max-w-sm">
          This section is restricted to platform administrators. Contact your admin if you need
          access.
        </p>
        <a href="/" className="text-sm text-primary-600 hover:underline">
          Return to dashboard
        </a>
      </div>
    )
  }

  return <Outlet />
}
