import { useState, useEffect, useCallback, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import {
  MagnifyingGlassIcon,
  BookOpenIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  AcademicCapIcon,
} from '@heroicons/react/24/outline'
import { learnApi } from '@/services/learnApi'
import type { LearnableContentItem } from '@/types/learn'

const CONTENT_TYPES = [
  '', 'case', 'simulation', 'osce_station', 'prescription_screening', 'drill', 'game',
]
const DIFFICULTIES = ['', '1', '2', '3', '4', '5']
const PAGE_SIZE = 20

const DIFFICULTY_LABEL: Record<string, string> = {
  '1': 'Beginner', '2': 'Easy', '3': 'Intermediate', '4': 'Hard', '5': 'Expert',
}
const TYPE_COLOR: Record<string, string> = {
  case: 'bg-blue-100 text-blue-700',
  simulation: 'bg-purple-100 text-purple-700',
  osce_station: 'bg-teal-100 text-teal-700',
  prescription_screening: 'bg-amber-100 text-amber-700',
  drill: 'bg-green-100 text-green-700',
  game: 'bg-pink-100 text-pink-700',
}
const DIFF_COLOR: Record<string, string> = {
  '1': 'bg-green-50 text-green-600', '2': 'bg-lime-50 text-lime-700',
  '3': 'bg-amber-50 text-amber-700', '4': 'bg-orange-50 text-orange-700',
  '5': 'bg-red-50 text-red-700',
}

function ContentCard({ item }: { item: LearnableContentItem }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 flex flex-col gap-3 hover:border-primary-300 hover:shadow-sm transition-all">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${TYPE_COLOR[item.content_type] ?? 'bg-gray-100 text-gray-600'}`}>
            {item.content_type.replace('_', ' ')}
          </span>
          {item.difficulty && (
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${DIFF_COLOR[item.difficulty] ?? 'bg-gray-100 text-gray-600'}`}>
              {DIFFICULTY_LABEL[item.difficulty] ?? `Level ${item.difficulty}`}
            </span>
          )}
        </div>
        {item.external_id && (
          <span className="text-xs font-mono text-gray-400 flex-shrink-0 truncate max-w-[100px]" title={item.external_id}>
            {item.external_id}
          </span>
        )}
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-900 leading-snug line-clamp-2" title={item.title}>
          {item.title}
        </h3>
        {item.domain && (
          <p className="text-xs text-gray-500 mt-1">{item.domain}</p>
        )}
      </div>

      <div className="mt-auto pt-1 flex items-center justify-between">
        <span className="text-xs text-gray-400">
          Published {new Date(item.published_at).toLocaleDateString()}
        </span>
        <Link
          to={`/learn/content/${item.id}`}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-white bg-primary-600 rounded-lg hover:bg-primary-700 transition-colors"
        >
          <AcademicCapIcon className="w-3.5 h-3.5" />
          Start training
        </Link>
      </div>
    </div>
  )
}

export default function TrainingLibraryPage() {
  const [searchParams] = useSearchParams()
  const [contentType, setContentType] = useState(searchParams.get('content_type') ?? '')
  const [difficulty, setDifficulty] = useState('')
  const [domain, setDomain] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<LearnableContentItem[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [loading, setLoading] = useState(true)
  // Prevents the page-change effect from firing a duplicate load on initial mount
  // (the filter-change effect already calls load(1) on mount).
  const didMountRef = useRef(false)

  const load = useCallback(async (pg: number) => {
    setLoading(true)
    try {
      const res = await learnApi.browse({
        content_type: contentType || undefined,
        domain: domain.trim() || undefined,
        difficulty: difficulty || undefined,
        search: search.trim() || undefined,
        page: pg,
        page_size: PAGE_SIZE,
      })
      setItems(res.items)
      setTotal(res.total)
      setPages(res.pages)
    } catch {
      toast.error('Failed to load training content.')
    } finally {
      setLoading(false)
    }
  }, [contentType, domain, difficulty, search])

  useEffect(() => {
    setPage(1)
    load(1)
  }, [contentType, difficulty]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // Skip initial mount — the filter effect above already called load(1).
    // After that, fire whenever the user navigates to a different page.
    if (!didMountRef.current) {
      didMountRef.current = true
      return
    }
    load(page)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page])

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    load(1)
  }

  return (
    <div className="space-y-5 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Training Library</h1>
        <p className="text-sm text-gray-500 mt-1">
          Browse published, clinically-approved training content.
        </p>
      </div>

      {/* Filters */}
      <form onSubmit={handleFilter} className="flex flex-wrap gap-3 items-end">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Content type</label>
          <select
            value={contentType}
            onChange={(e) => setContentType(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {CONTENT_TYPES.map((t) => (
              <option key={t} value={t}>{t ? t.replace('_', ' ') : 'All types'}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Difficulty</label>
          <select
            value={difficulty}
            onChange={(e) => setDifficulty(e.target.value)}
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {DIFFICULTIES.map((d) => (
              <option key={d} value={d}>{d ? `${DIFFICULTY_LABEL[d] ?? d}` : 'All levels'}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Domain</label>
          <input
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="e.g. Respiratory"
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 w-36 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Search</label>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Title or ID…"
            className="text-sm border border-gray-300 rounded-lg px-3 py-2 w-40 focus:outline-none focus:ring-2 focus:ring-primary-500"
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

      {/* Count */}
      <p className="text-xs text-gray-400">
        {loading ? 'Loading…' : `${total.toLocaleString()} item${total !== 1 ? 's' : ''} available`}
      </p>

      {/* Empty state */}
      {!loading && items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 bg-gray-50 rounded-xl border border-dashed border-gray-300">
          <BookOpenIcon className="w-12 h-12 text-gray-300 mb-3" />
          <p className="text-sm font-medium text-gray-500">No published learning content is available yet.</p>
          <p className="text-xs text-gray-400 mt-1 text-center max-w-xs">
            Content must be reviewed, approved, and published by an administrator before it appears here.
          </p>
        </div>
      )}

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-white border border-gray-200 rounded-xl p-5 space-y-3">
              <div className="h-4 w-20 bg-gray-100 animate-pulse rounded" />
              <div className="h-5 w-full bg-gray-100 animate-pulse rounded" />
              <div className="h-4 w-3/4 bg-gray-100 animate-pulse rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <ContentCard key={item.id} item={item} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <p className="text-xs text-gray-400">Page {page} of {pages}</p>
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
