import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { MagnifyingGlassIcon, FunnelIcon, ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
import { contentApi } from '@/services/governanceApi'
import StatusBadge from '@/components/governance/StatusBadge'
import ContentTypeBadge from '@/components/governance/ContentTypeBadge'
import RegionBadge from '@/components/governance/RegionBadge'
import type { ContentItemListItem } from '@/types/governance'

const STATUSES = [
  '', 'draft', 'imported', 'pending_review', 'clinically_approved',
  'published', 'unpublished', 'needs_update', 'retired',
]
const CONTENT_TYPES = [
  '', 'case', 'simulation', 'osce_station', 'prescription_screening',
  'drill', 'game', 'evidence_source', 'taxonomy_node',
]

const PER_PAGE = 20

export default function ContentLibraryPage() {
  const [items, setItems] = useState<ContentItemListItem[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)

  // Filters
  const [statusFilter, setStatusFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [domainFilter, setDomainFilter] = useState('')

  const load = useCallback(async (pg: number) => {
    setLoading(true)
    try {
      const res = await contentApi.list({
        page: pg,
        per_page: PER_PAGE,
        status: statusFilter || undefined,
        content_type: typeFilter || undefined,
        domain: domainFilter.trim() || undefined,
      })
      setItems(res.items)
      setTotal(res.total)
      setPages(res.pages)
    } catch {
      toast.error('Failed to load content items.')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, typeFilter, domainFilter])

  useEffect(() => {
    setPage(1)
    load(1)
  }, [statusFilter, typeFilter, domainFilter]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    load(page)
  }, [page, load])

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    load(1)
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <form onSubmit={handleFilter} className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s || 'All statuses'}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Content type</label>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white"
          >
            {CONTENT_TYPES.map((t) => (
              <option key={t} value={t}>{t || 'All types'}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1 flex items-center gap-1">
            <FunnelIcon className="w-3 h-3" /> Domain
          </label>
          <input
            type="text"
            value={domainFilter}
            onChange={(e) => setDomainFilter(e.target.value)}
            placeholder="e.g. Respiratory"
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 w-40"
          />
        </div>
        <button
          type="submit"
          className="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <MagnifyingGlassIcon className="w-4 h-4" />
          Apply
        </button>
      </form>

      {/* Total */}
      <p className="text-xs text-gray-400">
        {loading ? 'Loading…' : `${total.toLocaleString()} items`}
      </p>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  External ID
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Title
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Type
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Domain
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Regions
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Difficulty
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 8 }).map((__, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 bg-gray-100 animate-pulse rounded" />
                        </td>
                      ))}
                    </tr>
                  ))
                : items.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-gray-500 max-w-[100px] truncate">
                        {/* External ID is on ContentItemRead, not ListItem — show from title context */}
                        —
                      </td>
                      <td className="px-4 py-3 max-w-[240px]">
                        <p className="text-sm text-gray-900 font-medium truncate" title={item.title}>
                          {item.title}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <ContentTypeBadge contentType={item.content_type} />
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 max-w-[120px] truncate">
                        {item.domain ?? '—'}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {(item.region_scope ?? []).map((r) => (
                            <RegionBadge key={r} region={r} />
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500 text-center">
                        {item.difficulty ?? '—'}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          to={`/admin/governance/content/${item.id}`}
                          className="text-xs text-primary-600 hover:underline font-medium"
                        >
                          View →
                        </Link>
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-gray-400">
            Page {page} of {pages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="flex items-center gap-1 px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40"
            >
              <ChevronLeftIcon className="w-3 h-3" /> Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages || loading}
              className="flex items-center gap-1 px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40"
            >
              Next <ChevronRightIcon className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
