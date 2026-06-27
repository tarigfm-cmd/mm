import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import LoadingSpinner from '@/components/LoadingSpinner'
import ProtectedRoute from '@/components/ProtectedRoute'
import { useAuthInit } from '@/hooks/useAuthInit'

const Dashboard = lazy(() => import('@/pages/Dashboard'))
const MaterialsUpload = lazy(() => import('@/pages/MaterialsUpload'))
const ScenariosPage = lazy(() => import('@/pages/ScenariosPage'))
const ScenarioPage = lazy(() => import('@/pages/ScenarioPage'))
const OrganizationsPage = lazy(() => import('@/pages/OrganizationsPage'))
const OrgDetailPage = lazy(() => import('@/pages/OrgDetailPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <LoadingSpinner label="Loading…" />
    </div>
  )
}

function AppRoutes() {
  useAuthInit()

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/upload" element={<MaterialsUpload />} />
        <Route path="/scenarios" element={<ScenariosPage />} />
        <Route path="/scenarios/:id" element={<ScenarioPage />} />
        <Route path="/orgs" element={<OrganizationsPage />} />
        <Route path="/orgs/:slug" element={<OrgDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <AppRoutes />
      </Suspense>

      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: { fontSize: '0.875rem' },
          success: { iconTheme: { primary: '#16a34a', secondary: '#fff' } },
          error: { iconTheme: { primary: '#dc2626', secondary: '#fff' } },
        }}
      />
    </BrowserRouter>
  )
}
