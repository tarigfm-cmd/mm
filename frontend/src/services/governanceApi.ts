/**
 * Governance API client — covers content governance, import, evidence, and publishing.
 * All write operations are subject to backend RBAC; the frontend relies on backend 403
 * responses for non-superuser permission enforcement.
 */
import axios from 'axios'
import { useAppStore } from '@/store/appStore'
import { getOrCreateSessionId, getRefreshToken, setStoredRefreshToken, clearStoredRefreshToken } from '@/services/api'
import type {
  ApprovalBatchCreate,
  ApprovalBatchRead,
  ClinicalReviewCreate,
  ClinicalReviewRead,
  CommitResult,
  ContentItemCreate,
  ContentItemListResponse,
  ContentItemRead,
  ContentVersionRead,
  EvidenceSourceCreate,
  EvidenceSourceRead,
  EvidenceSourceUpdate,
  PreviewResult,
  PublicationRecordRead,
} from '@/types/governance'

const BASE_URL = ((import.meta as unknown) as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL ?? ''

// Shared axios instance with auth + session interceptors (mirrors api.ts pattern)
const govHttp = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

const govAuthHttp = axios.create({ baseURL: BASE_URL, timeout: 30_000 })

govHttp.interceptors.request.use((config) => {
  const { accessToken } = useAppStore.getState()
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  config.headers['X-Session-Id'] = getOrCreateSessionId()
  return config
})

let _refreshing = false
let _pending: Array<(token: string) => void> = []

govHttp.interceptors.response.use(
  (r) => r,
  async (err) => {
    const original = err.config as typeof err.config & { _retry?: boolean }
    const status = err.response?.status
    if (
      status === 401 &&
      !original._retry &&
      original.url &&
      !original.url.includes('/api/auth/')
    ) {
      original._retry = true
      if (_refreshing) {
        return new Promise<string>((res) => _pending.push(res)).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return govHttp(original)
        })
      }
      _refreshing = true
      try {
        const rt = getRefreshToken()
        if (!rt) throw new Error('no refresh token')
        const { data } = await govAuthHttp.post('/api/auth/refresh', { refresh_token: rt })
        useAppStore.getState().setAccessToken(data.access_token)
        setStoredRefreshToken(data.refresh_token)
        _pending.forEach((cb) => cb(data.access_token))
        _pending = []
        original.headers.Authorization = `Bearer ${data.access_token}`
        return govHttp(original)
      } catch {
        _pending = []
        useAppStore.getState().clearAuth()
        clearStoredRefreshToken()
        window.location.replace('/login')
        return Promise.reject(err)
      } finally {
        _refreshing = false
      }
    }
    return Promise.reject(err)
  },
)

// ── Import ─────────────────────────────────────────────────────────────────

export const importApi = {
  preview: async (file: File): Promise<PreviewResult> => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await govHttp.post<PreviewResult>('/api/content/import/preview', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300_000,
    })
    return data
  },

  commit: async (file: File, approvalBatchId?: string): Promise<CommitResult> => {
    const form = new FormData()
    form.append('file', file)
    if (approvalBatchId) form.append('approval_batch_id', approvalBatchId)
    const { data } = await govHttp.post<CommitResult>('/api/content/import/commit', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600_000,
    })
    return data
  },
}

// ── Approval Batches ───────────────────────────────────────────────────────

export const approvalBatchApi = {
  list: async (): Promise<ApprovalBatchRead[]> => {
    const { data } = await govHttp.get<ApprovalBatchRead[]>('/api/content/approval-batches')
    return data
  },

  create: async (body: ApprovalBatchCreate): Promise<ApprovalBatchRead> => {
    const { data } = await govHttp.post<ApprovalBatchRead>('/api/content/approval-batches', body)
    return data
  },
}

// ── Content Items ──────────────────────────────────────────────────────────

export const contentApi = {
  list: async (params?: {
    page?: number
    per_page?: number
    content_type?: string
    status?: string
    domain?: string
  }): Promise<ContentItemListResponse> => {
    const { data } = await govHttp.get<ContentItemListResponse>('/api/content/items', { params })
    return data
  },

  get: async (id: string): Promise<ContentItemRead> => {
    const { data } = await govHttp.get<ContentItemRead>(`/api/content/items/${id}`)
    return data
  },

  create: async (body: ContentItemCreate): Promise<ContentItemRead> => {
    const { data } = await govHttp.post<ContentItemRead>('/api/content/items', body)
    return data
  },

  listVersions: async (itemId: string): Promise<ContentVersionRead[]> => {
    const { data } = await govHttp.get<ContentVersionRead[]>(
      `/api/content/items/${itemId}/versions`,
    )
    return data
  },

  rollback: async (itemId: string, versionId: string): Promise<ContentVersionRead> => {
    const { data } = await govHttp.post<ContentVersionRead>(
      `/api/content/items/${itemId}/versions/rollback/${versionId}`,
    )
    return data
  },

  listReviews: async (itemId: string): Promise<ClinicalReviewRead[]> => {
    const { data } = await govHttp.get<ClinicalReviewRead[]>(
      `/api/content/items/${itemId}/reviews`,
    )
    return data
  },

  createReview: async (itemId: string, body: ClinicalReviewCreate): Promise<ClinicalReviewRead> => {
    const { data } = await govHttp.post<ClinicalReviewRead>(
      `/api/content/items/${itemId}/reviews`,
      body,
    )
    return data
  },

  publish: async (
    itemId: string,
    regionCode: string,
    reason?: string,
  ): Promise<PublicationRecordRead> => {
    const { data } = await govHttp.post<PublicationRecordRead>(
      `/api/content/items/${itemId}/publish`,
      { region_code: regionCode, reason },
    )
    return data
  },

  unpublish: async (
    itemId: string,
    regionCode: string,
    reason?: string,
  ): Promise<PublicationRecordRead> => {
    const { data } = await govHttp.post<PublicationRecordRead>(
      `/api/content/items/${itemId}/unpublish`,
      { region_code: regionCode, reason },
    )
    return data
  },
}

// ── Evidence Sources ───────────────────────────────────────────────────────

export const evidenceApi = {
  list: async (params?: {
    region?: string
    evidence_status?: string
  }): Promise<EvidenceSourceRead[]> => {
    const { data } = await govHttp.get<EvidenceSourceRead[]>('/api/evidence/sources', { params })
    return data
  },

  create: async (body: EvidenceSourceCreate): Promise<EvidenceSourceRead> => {
    const { data } = await govHttp.post<EvidenceSourceRead>('/api/evidence/sources', body)
    return data
  },

  update: async (id: string, body: EvidenceSourceUpdate): Promise<EvidenceSourceRead> => {
    const { data } = await govHttp.patch<EvidenceSourceRead>(`/api/evidence/sources/${id}`, body)
    return data
  },

  dueForReview: async (): Promise<EvidenceSourceRead[]> => {
    const { data } = await govHttp.get<EvidenceSourceRead[]>('/api/evidence/due-for-review')
    return data
  },
}
