import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import {
  ArrowLeftIcon,
  ClockIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import { contentApi } from '@/services/governanceApi'
import StatusBadge from '@/components/governance/StatusBadge'
import ContentTypeBadge from '@/components/governance/ContentTypeBadge'
import RegionBadge from '@/components/governance/RegionBadge'
import ConfirmActionDialog from '@/components/governance/ConfirmActionDialog'
import type {
  ContentItemRead,
  ContentVersionRead,
  ClinicalReviewRead,
  ClinicalReviewCreate,
  ReviewDecision,
} from '@/types/governance'

const REGIONS = ['UK', 'US', 'GCC', 'AU'] as const
const REVIEW_DECISIONS: ReviewDecision[] = [
  'approved', 'approved_with_conditions', 'rejected', 'needs_revision',
]

export default function ContentDetailPage() {
  const { id } = useParams<{ id: string }>()

  const [item, setItem] = useState<ContentItemRead | null>(null)
  const [versions, setVersions] = useState<ContentVersionRead[]>([])
  const [reviews, setReviews] = useState<ClinicalReviewRead[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Review form
  const [showReviewForm, setShowReviewForm] = useState(false)
  const [reviewForm, setReviewForm] = useState<ClinicalReviewCreate>({ review_decision: 'approved' })
  const [savingReview, setSavingReview] = useState(false)

  // Publish/unpublish
  const [publishRegion, setPublishRegion] = useState<string>('')
  const [publishReason, setPublishReason] = useState('')
  const [publishConfirm, setPublishConfirm] = useState(false)
  const [unpublishConfirm, setUnpublishConfirm] = useState(false)
  const [actioning, setActioning] = useState(false)

  // Rollback
  const [rollbackVersionId, setRollbackVersionId] = useState<string | null>(null)
  const [rollbackConfirm, setRollbackConfirm] = useState(false)
  const [rollingBack, setRollingBack] = useState(false)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    Promise.all([
      contentApi.get(id),
      contentApi.listVersions(id).catch(() => []),
      contentApi.listReviews(id).catch(() => []),
    ])
      .then(([itemData, versionData, reviewData]) => {
        setItem(itemData)
        setVersions(versionData)
        setReviews(reviewData)
      })
      .catch(() => setError('Failed to load content item.'))
      .finally(() => setLoading(false))
  }, [id])

  const submitReview = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!id) return
    setSavingReview(true)
    try {
      const review = await contentApi.createReview(id, reviewForm)
      setReviews((prev) => [review, ...prev])
      toast.success('Review submitted.')
      setShowReviewForm(false)
      setReviewForm({ review_decision: 'approved' })
      const refreshed = await contentApi.get(id)
      setItem(refreshed)
    } catch {
      toast.error('Failed to submit review.')
    } finally {
      setSavingReview(false)
    }
  }

  const handlePublish = async () => {
    if (!id || !publishRegion) return
    setActioning(true)
    try {
      await contentApi.publish(id, publishRegion, publishReason || undefined)
      toast.success(`Published to ${publishRegion}`)
      const refreshed = await contentApi.get(id)
      setItem(refreshed)
    } catch {
      toast.error('Publish failed. Item may need an approved clinical review.')
    } finally {
      setActioning(false)
      setPublishConfirm(false)
      setPublishReason('')
    }
  }

  const handleUnpublish = async () => {
    if (!id || !publishRegion) return
    setActioning(true)
    try {
      await contentApi.unpublish(id, publishRegion, publishReason || undefined)
      toast.success(`Unpublished from ${publishRegion}`)
      const refreshed = await contentApi.get(id)
      setItem(refreshed)
    } catch {
      toast.error('Unpublish failed.')
    } finally {
      setActioning(false)
      setUnpublishConfirm(false)
      setPublishReason('')
    }
  }

  const handleRollback = async () => {
    if (!id || !rollbackVersionId) return
    setRollingBack(true)
    try {
      const newVer = await contentApi.rollback(id, rollbackVersionId)
      setVersions((prev) => [newVer, ...prev.map((v) => ({ ...v, is_current: false }))])
      toast.success(`Rolled back to version ${newVer.version_number - 1}`)
      const refreshed = await contentApi.get(id)
      setItem(refreshed)
    } catch {
      toast.error('Rollback failed.')
    } finally {
      setRollingBack(false)
      setRollbackConfirm(false)
      setRollbackVersionId(null)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-6 w-48 bg-gray-100 rounded" />
        <div className="h-40 bg-gray-100 rounded-xl" />
      </div>
    )
  }

  if (error || !item) {
    return (
      <div className="text-center py-12 text-gray-400">
        <p className="text-sm">{error ?? 'Item not found.'}</p>
        <Link to="/admin/governance/content" className="mt-2 text-xs text-primary-600 hover:underline block">
          ← Back to content library
        </Link>
      </div>
    )
  }

  const currentVersion = versions.find((v) => v.is_current)
  const olderVersions = versions.filter((v) => !v.is_current)
  const hasApprovedReview = reviews.some((r) =>
    ['approved', 'approved_with_conditions'].includes(r.review_decision),
  )

  return (
    <div className="max-w-4xl space-y-6">
      {/* Breadcrumb */}
      <Link
        to="/admin/governance/content"
        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 w-fit"
      >
        <ArrowLeftIcon className="w-3 h-3" /> Content Library
      </Link>

      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-xl p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <ContentTypeBadge contentType={item.content_type} />
              <StatusBadge status={item.status} size="md" />
            </div>
            <h2 className="text-xl font-bold text-gray-900 mt-2">{item.title}</h2>
            {item.external_id && (
              <p className="text-xs font-mono text-gray-400 mt-1">{item.external_id}</p>
            )}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
          <Row label="Domain" value={item.domain ?? '—'} />
          <Row label="Specialty" value={item.specialty ?? '—'} />
          <Row label="Difficulty" value={item.difficulty ?? '—'} />
          <Row
            label="Regions"
            value={
              <div className="flex flex-wrap gap-1 mt-0.5">
                {(item.region_scope ?? []).map((r) => <RegionBadge key={r} region={r} />)}
              </div>
            }
          />
          <Row label="Created" value={new Date(item.created_at).toLocaleString()} />
          <Row label="Updated" value={new Date(item.updated_at).toLocaleString()} />
          {item.current_version_id && (
            <Row label="Current version ID" value={
              <span className="font-mono text-xs">{item.current_version_id}</span>
            } />
          )}
        </div>
      </div>

      {/* Versions */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <ClockIcon className="w-4 h-4 text-gray-400" />
          Version history ({versions.length})
        </h3>
        <div className="space-y-2">
          {versions.length === 0 && (
            <p className="text-sm text-gray-400">No versions yet.</p>
          )}
          {currentVersion && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-blue-800">
                    v{currentVersion.version_number} — Current
                  </p>
                  <p className="text-xs text-blue-600 mt-0.5">
                    {currentVersion.change_summary ?? 'No summary'} ·{' '}
                    {new Date(currentVersion.created_at).toLocaleString()}
                  </p>
                  {currentVersion.source_file_name && (
                    <p className="text-xs text-blue-500 font-mono mt-0.5">
                      {currentVersion.source_file_name}
                      {currentVersion.source_row_number != null
                        ? ` row ${currentVersion.source_row_number}`
                        : ''}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
          {olderVersions.map((v) => (
            <div key={v.id} className="bg-gray-50 border border-gray-200 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-700">v{v.version_number}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {v.change_summary ?? 'No summary'} ·{' '}
                    {new Date(v.created_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={() => { setRollbackVersionId(v.id); setRollbackConfirm(true) }}
                  className="flex items-center gap-1 text-xs text-amber-600 hover:text-amber-800 border border-amber-300 rounded-lg px-3 py-1.5 hover:bg-amber-50 transition-colors"
                >
                  <ArrowPathIcon className="w-3 h-3" /> Rollback to v{v.version_number}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Clinical reviews */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700">
            Clinical reviews ({reviews.length})
          </h3>
          <button
            onClick={() => setShowReviewForm((s) => !s)}
            className="text-xs text-primary-600 hover:underline"
          >
            {showReviewForm ? 'Cancel' : '+ Submit review'}
          </button>
        </div>

        {showReviewForm && (
          <form
            onSubmit={submitReview}
            className="bg-white border border-gray-200 rounded-xl p-5 mb-4 space-y-4"
          >
            <h4 className="text-sm font-semibold text-gray-700">Submit clinical review</h4>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Decision <span className="text-red-500">*</span>
                </label>
                <select
                  value={reviewForm.review_decision}
                  onChange={(e) =>
                    setReviewForm((f) => ({
                      ...f,
                      review_decision: e.target.value as ReviewDecision,
                    }))
                  }
                  className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  {REVIEW_DECISIONS.map((d) => (
                    <option key={d} value={d}>{d.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Reviewer role
                </label>
                <input
                  type="text"
                  value={reviewForm.reviewer_role ?? ''}
                  onChange={(e) => setReviewForm((f) => ({ ...f, reviewer_role: e.target.value }))}
                  className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  placeholder="e.g. clinical_pharmacist"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Comments</label>
              <textarea
                rows={3}
                value={reviewForm.comments ?? ''}
                onChange={(e) => setReviewForm((f) => ({ ...f, comments: e.target.value }))}
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
                placeholder="Clinical accuracy assessment, safety notes, localization comments…"
              />
            </div>

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowReviewForm(false)}
                className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={savingReview}
                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {savingReview ? 'Saving…' : 'Submit Review'}
              </button>
            </div>
          </form>
        )}

        {reviews.length === 0 ? (
          <p className="text-sm text-gray-400">No clinical reviews yet.</p>
        ) : (
          <div className="space-y-2">
            {reviews.map((r) => {
              const approved = ['approved', 'approved_with_conditions'].includes(r.review_decision)
              return (
                <div
                  key={r.id}
                  className={`border rounded-xl p-4 ${
                    approved ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-white'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-2">
                      {approved ? (
                        <CheckCircleIcon className="w-4 h-4 text-green-600 flex-shrink-0" />
                      ) : (
                        <XCircleIcon className="w-4 h-4 text-red-400 flex-shrink-0" />
                      )}
                      <span className="text-sm font-semibold text-gray-800 capitalize">
                        {r.review_decision.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <span className="text-xs text-gray-400 flex-shrink-0">
                      {new Date(r.created_at).toLocaleString()}
                    </span>
                  </div>
                  {r.reviewer_role && (
                    <p className="text-xs text-gray-500 mt-1">Role: {r.reviewer_role}</p>
                  )}
                  {r.reviewer_team_name && (
                    <p className="text-xs text-gray-500">Team: {r.reviewer_team_name}</p>
                  )}
                  {r.comments && (
                    <p className="text-xs text-gray-600 mt-2 italic">{r.comments}</p>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* Publishing */}
      <section>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Publish / Unpublish</h3>

        {!hasApprovedReview && item.status !== 'published' && (
          <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 mb-4">
            Publish requires at least one approved clinical review for this item.
          </div>
        )}

        <div className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">
              Select region <span className="text-red-500">*</span>
            </label>
            <div className="flex gap-2 flex-wrap">
              {REGIONS.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setPublishRegion(r)}
                  className={`px-4 py-2 text-sm font-semibold rounded-lg border transition-colors ${
                    publishRegion === r
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:border-primary-400'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Reason (optional)</label>
            <input
              type="text"
              value={publishReason}
              onChange={(e) => setPublishReason(e.target.value)}
              className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Optional note"
            />
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => setPublishConfirm(true)}
              disabled={!publishRegion || actioning}
              className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-40 transition-colors"
            >
              Publish to {publishRegion || '…'}
            </button>
            <button
              onClick={() => setUnpublishConfirm(true)}
              disabled={!publishRegion || actioning}
              className="px-4 py-2 text-sm font-medium text-white bg-gray-500 rounded-lg hover:bg-gray-600 disabled:opacity-40 transition-colors"
            >
              Unpublish from {publishRegion || '…'}
            </button>
          </div>
        </div>
      </section>

      {/* Confirm dialogs */}
      <ConfirmActionDialog
        open={publishConfirm}
        title={`Publish to ${publishRegion}?`}
        description={
          <p>
            This will publish <strong>{item.title}</strong> to the{' '}
            <strong>{publishRegion}</strong> region. Ensure a clinical review is approved.
          </p>
        }
        confirmLabel="Publish"
        confirmVariant="primary"
        loading={actioning}
        onConfirm={handlePublish}
        onCancel={() => setPublishConfirm(false)}
      />

      <ConfirmActionDialog
        open={unpublishConfirm}
        title={`Unpublish from ${publishRegion}?`}
        description={
          <p>
            This will unpublish <strong>{item.title}</strong> from{' '}
            <strong>{publishRegion}</strong>. The item will return to unpublished status.
          </p>
        }
        confirmLabel="Unpublish"
        confirmVariant="danger"
        loading={actioning}
        onConfirm={handleUnpublish}
        onCancel={() => setUnpublishConfirm(false)}
      />

      <ConfirmActionDialog
        open={rollbackConfirm}
        title="Rollback to this version?"
        description={
          <p>
            A new version will be created as a copy of the selected version. The item will return to{' '}
            <span className="font-mono">pending_review</span> or{' '}
            <span className="font-mono">needs_update</span> status and require re-review.
          </p>
        }
        confirmLabel="Rollback"
        confirmVariant="warning"
        loading={rollingBack}
        onConfirm={handleRollback}
        onCancel={() => { setRollbackConfirm(false); setRollbackVersionId(null) }}
      />
    </div>
  )
}

function Row({
  label,
  value,
}: {
  label: string
  value: React.ReactNode
}) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <div className="text-sm text-gray-800 mt-0.5">{value}</div>
    </div>
  )
}
