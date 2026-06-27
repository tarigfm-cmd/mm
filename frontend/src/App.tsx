import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Navigation from '@/components/Navigation'
import LoadingSpinner from '@/components/LoadingSpinner'

const Dashboard = lazy(() => import('@/pages/Dashboard'))
const MaterialsUpload = lazy(() => import('@/pages/MaterialsUpload'))
const ScenariosPage = lazy(() => import('@/pages/ScenariosPage'))
const ScenarioPage = lazy(() => import('@/pages/ScenarioPage'))

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <LoadingSpinner label="Loading…" />
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <Navigation />

        <main className="ml-64 min-h-screen">
          <div className="max-w-7xl mx-auto px-8 py-8">
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/upload" element={<MaterialsUpload />} />
                <Route path="/scenarios" element={<ScenariosPage />} />
                <Route path="/scenarios/:id" element={<ScenarioPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </div>
        </main>

        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: { fontSize: '0.875rem' },
            success: { iconTheme: { primary: '#16a34a', secondary: '#fff' } },
            error: { iconTheme: { primary: '#dc2626', secondary: '#fff' } },
          }}
        />
      </div>
    </BrowserRouter>
  )
}
