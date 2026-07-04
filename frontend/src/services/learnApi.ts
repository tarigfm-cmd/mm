/**
 * Learner API client — published content browse, detail, training sessions, progress.
 * All endpoints require authentication. Only published content is returned.
 */
import axios from 'axios'
import { useAppStore } from '@/store/appStore'
import { getOrCreateSessionId, getRefreshToken, setStoredRefreshToken, clearStoredRefreshToken } from '@/services/api'
import type {
  LearnableContentDetail,
  LearnableContentListResponse,
  LearnerAttemptCreate,
  LearnerAttemptResult,
  LearnerProgressSummary,
  SessionStartResponse,
  SessionSubmitRequest,
  SessionSubmitResponse,
  TrainingFlowResponse,
} from '@/types/learn'

const BASE_URL = ((import.meta as unknown) as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL ?? ''

const learnHttp = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})
const learnAuthHttp = axios.create({ baseURL: BASE_URL, timeout: 30_000 })

learnHttp.interceptors.request.use((config) => {
  const { accessToken } = useAppStore.getState()
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  config.headers['X-Session-Id'] = getOrCreateSessionId()
  return config
})

let _refreshing = false
let _pending: Array<(token: string) => void> = []

learnHttp.interceptors.response.use(
  (r) => r,
  async (err) => {
    const original = err.config as typeof err.config & { _retry?: boolean }
    const status = err.response?.status
    if (status === 401 && !original._retry && original.url && !original.url.includes('/api/auth/')) {
      original._retry = true
      if (_refreshing) {
        return new Promise<string>((res) => _pending.push(res)).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return learnHttp(original)
        })
      }
      _refreshing = true
      try {
        const rt = getRefreshToken()
        if (!rt) throw new Error('no refresh token')
        const { data } = await learnAuthHttp.post('/api/auth/refresh', { refresh_token: rt })
        useAppStore.getState().setAccessToken(data.access_token)
        setStoredRefreshToken(data.refresh_token)
        _pending.forEach((cb) => cb(data.access_token))
        _pending = []
        original.headers.Authorization = `Bearer ${data.access_token}`
        return learnHttp(original)
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

export const learnApi = {
  browse: async (params: {
    region_code?: string
    content_type?: string
    domain?: string
    difficulty?: string
    search?: string
    page?: number
    page_size?: number
  }): Promise<LearnableContentListResponse> => {
    const { data } = await learnHttp.get<LearnableContentListResponse>('/api/learn/content', { params })
    return data
  },

  getDetail: async (id: string, regionCode?: string): Promise<LearnableContentDetail> => {
    const params = regionCode ? { region_code: regionCode } : undefined
    const { data } = await learnHttp.get<LearnableContentDetail>(`/api/learn/content/${id}`, { params })
    return data
  },

  getTrainingFlow: async (id: string, regionCode?: string): Promise<TrainingFlowResponse> => {
    const params = regionCode ? { region_code: regionCode } : undefined
    const { data } = await learnHttp.get<TrainingFlowResponse>(
      `/api/learn/content/${id}/training-flow`,
      { params },
    )
    return data
  },

  startSession: async (id: string, regionCode?: string): Promise<SessionStartResponse> => {
    const body = regionCode ? { region_code: regionCode } : {}
    const { data } = await learnHttp.post<SessionStartResponse>(
      `/api/learn/content/${id}/sessions`,
      body,
    )
    return data
  },

  submitSession: async (
    sessionId: string,
    body: SessionSubmitRequest,
  ): Promise<SessionSubmitResponse> => {
    const { data } = await learnHttp.post<SessionSubmitResponse>(
      `/api/learn/sessions/${sessionId}/submit`,
      body,
    )
    return data
  },

  // Phase-1 single-attempt endpoint (kept for compatibility)
  submitAttempt: async (id: string, body: LearnerAttemptCreate): Promise<LearnerAttemptResult> => {
    const { data } = await learnHttp.post<LearnerAttemptResult>(
      `/api/learn/content/${id}/attempt`,
      body,
    )
    return data
  },

  getProgress: async (): Promise<LearnerProgressSummary> => {
    const { data } = await learnHttp.get<LearnerProgressSummary>('/api/learn/progress')
    return data
  },
}
