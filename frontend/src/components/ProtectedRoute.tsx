import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAppStore } from '@/store/appStore'
import Navigation from '@/components/Navigation'
import LoadingSpinner from '@/components/LoadingSpinner'

export default function ProtectedRoute() {
  const { currentUser, authInitialized } = useAppStore()
  const location = useLocation()

  if (!authInitialized) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <LoadingSpinner size="lg" label="Loading…" />
      </div>
    )
  }

  if (!currentUser) {
    return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      <main className="ml-64 min-h-screen">
        <div className="max-w-7xl mx-auto px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
