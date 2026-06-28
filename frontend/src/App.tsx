import { Suspense, lazy } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import LoadingSpinner from '@/components/LoadingSpinner'
import ProtectedRoute from '@/components/ProtectedRoute'
import AdminRoute from '@/components/AdminRoute'
import { useAuthInit } from '@/hooks/useAuthInit'

const Dashboard = lazy(() => import('@/pages/Dashboard'))
const MaterialsUpload = lazy(() => import('@/pages/MaterialsUpload'))
const ScenariosPage = lazy(() => import('@/pages/ScenariosPage'))
const ScenarioPage = lazy(() => import('@/pages/ScenarioPage'))
const OrganizationsPage = lazy(() => import('@/pages/OrganizationsPage'))
const OrgDetailPage = lazy(() => import('@/pages/OrgDetailPage'))
const ProgressPage = lazy(() => import('@/pages/ProgressPage'))
const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))

// Learner training pages
const TrainingLibraryPage = lazy(() => import('@/pages/learn/TrainingLibraryPage'))
const TrainingDetailPage = lazy(() => import('@/pages/learn/TrainingDetailPage'))
const TrainingProgressPage = lazy(() => import('@/pages/learn/TrainingProgressPage'))

// Governance admin pages
const GovernanceLayout = lazy(() => import('@/components/governance/GovernanceLayout'))
const GovernanceDashboard = lazy(() => import('@/pages/governance/GovernanceDashboard'))
const ImportCenter = lazy(() => import('@/pages/governance/ImportCenter'))
const ApprovalBatchesPage = lazy(() => import('@/pages/governance/ApprovalBatchesPage'))
const ContentLibraryPage = lazy(() => import('@/pages/governance/ContentLibraryPage'))
const ContentDetailPage = lazy(() => import('@/pages/governance/ContentDetailPage'))
const EvidenceManagementPage = lazy(() => import('@/pages/governance/EvidenceManagementPage'))
const RegionRulesPage = lazy(() => import('@/pages/governance/RegionRulesPage'))

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
        <Route path="/progress" element={<ProgressPage />} />

        {/* Learner training routes */}
        <Route path="/learn/content" element={<TrainingLibraryPage />} />
        <Route path="/learn/content/:id" element={<TrainingDetailPage />} />
        <Route path="/learn/progress" element={<TrainingProgressPage />} />

        {/* Admin-only governance routes */}
        <Route element={<AdminRoute />}>
          <Route path="/admin/governance" element={<GovernanceLayout />}>
            <Route index element={<GovernanceDashboard />} />
            <Route path="import" element={<ImportCenter />} />
            <Route path="approval-batches" element={<ApprovalBatchesPage />} />
            <Route path="content" element={<ContentLibraryPage />} />
            <Route path="content/:id" element={<ContentDetailPage />} />
            <Route path="evidence" element={<EvidenceManagementPage />} />
            <Route path="regions" element={<RegionRulesPage />} />
          </Route>
        </Route>

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
