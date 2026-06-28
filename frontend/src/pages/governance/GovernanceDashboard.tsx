import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowUpTrayIcon,
  CheckBadgeIcon,
  DocumentMagnifyingGlassIcon,
  BookOpenIcon,
  ExclamationCircleIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline'
import StatCard from '@/components/governance/StatCard'
import { contentApi, approvalBatchApi, evidenceApi } from '@/services/governanceApi'
import type { ApprovalBatchRead, EvidenceSourceRead } from '@/types/governance'

interface StatusCounts {
  total: number
  pending_review: number
  clinically_approved: number
  published: number
  needs_update: number
}

const QUICK_LINKS = [
  { to: '/admin/governance/import',           label: 'Import Package',       icon: ArrowUpTrayIcon,           desc: 'Upload & preview CSV/ZIP' },
  { to: '/admin/governance/approval-batches', label: 'Approval Batches',     icon: CheckBadgeIcon,            desc: 'Record pharmacist sign-offs' },
  { to: '/admin/governance/content',          label: 'Content Library',      icon: DocumentMagnifyingGlassIcon,desc: 'Browse & review items' },
  { to: '/admin/governance/evidence',         label: 'Evidence Sources',     icon: BookOpenIcon,              desc: 'Manage clinical evidence' },
]

export default function GovernanceDashboard() {
  const [counts, setCounts] = useState<StatusCounts | null>(null)
  const [dueEvidence, setDueEvidence] = useState<EvidenceSourceRead[]>([])
  const [recentBatches, setRecentBatches] = useState<ApprovalBatchRead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const [total, pending, approved, published, needsUpdate, batches, due] = await Promise.all([
          contentApi.list({ page: 1, per_page: 1 }),
          contentApi.list({ page: 1, per_page: 1, status: 'pending_review' }),
          contentApi.list({ page: 1, per_page: 1, status: 'clinically_approved' }),
          contentApi.list({ page: 1, per_page: 1, status: 'published' }),
          contentApi.list({ page: 1, per_page: 1, status: 'needs_update' }),
          approvalBatchApi.list().catch(() => [] as ApprovalBatchRead[]),
          evidenceApi.dueForReview().catch(() => [] as EvidenceSourceRead[]),
        ])
        if (!cancelled) {
          setCounts({
            total: total.total,
            pending_review: pending.total,
            clinically_approved: approved.total,
            published: published.total,
            needs_update: needsUpdate.total,
          })
          setRecentBatches(batches.slice(0, 5))
          setDueEvidence(due.slice(0, 5))
        }
      } catch {
        if (!cancelled) setError('Failed to load dashboard data. Check your permissions.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="space-y-8">
      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <ExclamationCircleIcon className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Stats grid */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Content items
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total items"
            value={loading ? '—' : (counts?.total ?? 0).toLocaleString()}
            icon={<ClipboardDocumentListIcon className="w-5 h-5" />}
            accent="blue"
            loading={loading}
          />
          <StatCard
            title="Pending review"
            value={loading ? '—' : (counts?.pending_review ?? 0).toLocaleString()}
            icon={<ExclamationCircleIcon className="w-5 h-5" />}
            accent="amber"
            loading={loading}
          />
          <StatCard
            title="Clinically approved"
            value={loading ? '—' : (counts?.clinically_approved ?? 0).toLocaleString()}
            icon={<CheckBadgeIcon className="w-5 h-5" />}
            accent="green"
            loading={loading}
          />
          <StatCard
            title="Published"
            value={loading ? '—' : (counts?.published ?? 0).toLocaleString()}
            icon={<BookOpenIcon className="w-5 h-5" />}
            accent="green"
            loading={loading}
          />
        </div>
        {!loading && counts && counts.needs_update > 0 && (
          <div className="mt-2 text-xs text-orange-600">
            {counts.needs_update} item{counts.needs_update !== 1 ? 's' : ''} need re-review after version update.
          </div>
        )}
      </div>

      {/* Quick links */}
      <div>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Quick actions
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {QUICK_LINKS.map(({ to, label, icon: Icon, desc }) => (
            <Link
              key={to}
              to={to}
              className="flex flex-col gap-2 p-4 bg-white border border-gray-200 rounded-xl hover:border-primary-300 hover:bg-primary-50 transition-colors group"
            >
              <div className="w-9 h-9 bg-primary-50 group-hover:bg-primary-100 rounded-lg flex items-center justify-center">
                <Icon className="w-5 h-5 text-primary-600" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-800">{label}</p>
                <p className="text-xs text-gray-400 mt-0.5">{desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Evidence due for review */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-700">Evidence due for review</h2>
            <Link
              to="/admin/governance/evidence"
              className="text-xs text-primary-600 hover:underline"
            >
              View all
            </Link>
          </div>
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-8 bg-gray-100 animate-pulse rounded" />
              ))}
            </div>
          ) : dueEvidence.length === 0 ? (
            <p className="text-sm text-gray-400">No evidence sources overdue for review.</p>
          ) : (
            <ul className="space-y-2">
              {dueEvidence.map((ev) => (
                <li key={ev.id} className="flex items-center justify-between text-sm">
                  <span className="truncate text-gray-700 max-w-[200px]" title={ev.title}>
                    {ev.title}
                  </span>
                  <span className="text-xs text-red-600 flex-shrink-0 ml-2">
                    {ev.next_review_due_at
                      ? new Date(ev.next_review_due_at).toLocaleDateString()
                      : 'Overdue'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Recent approval batches */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-700">Recent approval batches</h2>
            <Link
              to="/admin/governance/approval-batches"
              className="text-xs text-primary-600 hover:underline"
            >
              View all
            </Link>
          </div>
          {loading ? (
            <div className="space-y-2">
              {[1, 2].map((i) => (
                <div key={i} className="h-10 bg-gray-100 animate-pulse rounded" />
              ))}
            </div>
          ) : recentBatches.length === 0 ? (
            <p className="text-sm text-gray-400">
              No approval batches yet.{' '}
              <Link to="/admin/governance/approval-batches" className="text-primary-600 hover:underline">
                Create one
              </Link>{' '}
              before committing externally-approved content.
            </p>
          ) : (
            <ul className="space-y-3">
              {recentBatches.map((b) => (
                <li key={b.id} className="text-sm">
                  <p className="font-medium text-gray-800 truncate">{b.batch_name}</p>
                  <p className="text-xs text-gray-400">
                    {b.approved_by_team_name} ·{' '}
                    {new Date(b.approved_at).toLocaleDateString()} ·{' '}
                    {b.content_count != null ? `${b.content_count} items` : ''}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
