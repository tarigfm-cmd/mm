import axios, { AxiosError, type AxiosInstance } from 'axios'
import toast from 'react-hot-toast'
import type {
  GenerateScenarioRequest,
  Interaction,
  MaterialDetail,
  MaterialListResponse,
  Scenario,
  ScenarioInteractionsResponse,
  ScenarioListResponse,
  SubmitAnswerRequest,
} from '@/types'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const BASE_URL = (import.meta as any).env?.VITE_API_URL ?? ''

const http: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000, // 2 min — AI calls can take time
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor: attach session ID ────────────────────────────────────
http.interceptors.request.use((config) => {
  const sessionId = getOrCreateSessionId()
  config.headers['X-Session-Id'] = sessionId
  return config
})

// ── Response interceptor: surface errors as toasts ────────────────────────────
http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail: string }>) => {
    const message =
      error.response?.data?.detail ?? error.message ?? 'An unexpected error occurred.'
    const detail = typeof message === 'string' ? message : JSON.stringify(message)
    if (error.response?.status !== 404) {
      toast.error(detail, { duration: 5000 })
    }
    return Promise.reject(error)
  },
)

// ── Session management ────────────────────────────────────────────────────────
export function getOrCreateSessionId(): string {
  const key = 'pharmacy_ai_session_id'
  let id = localStorage.getItem(key)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(key, id)
  }
  return id
}

// ── Materials API ─────────────────────────────────────────────────────────────

export const materialsApi = {
  upload: async (
    file: File,
    title: string,
    description: string,
    onProgress?: (pct: number) => void,
  ): Promise<MaterialDetail> => {
    const form = new FormData()
    form.append('file', file)
    form.append('title', title)
    form.append('description', description)

    const { data } = await http.post<MaterialDetail>('/api/materials/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total))
        }
      },
    })
    return data
  },

  list: async (page = 1, perPage = 20): Promise<MaterialListResponse> => {
    const { data } = await http.get<MaterialListResponse>('/api/materials', {
      params: { page, per_page: perPage },
    })
    return data
  },

  get: async (id: string): Promise<MaterialDetail> => {
    const { data } = await http.get<MaterialDetail>(`/api/materials/${id}`)
    return data
  },

  delete: async (id: string): Promise<void> => {
    await http.delete(`/api/materials/${id}`)
  },
}

// ── Scenarios API ─────────────────────────────────────────────────────────────

export const scenariosApi = {
  generate: async (request: GenerateScenarioRequest): Promise<Scenario> => {
    const { data } = await http.post<Scenario>('/api/scenarios/generate', request)
    return data
  },

  list: async (params?: {
    page?: number
    per_page?: number
    difficulty?: string
    material_id?: string
  }): Promise<ScenarioListResponse> => {
    const { data } = await http.get<ScenarioListResponse>('/api/scenarios', { params })
    return data
  },

  get: async (id: string): Promise<Scenario> => {
    const { data } = await http.get<Scenario>(`/api/scenarios/${id}`)
    return data
  },

  submitAnswer: async (
    scenarioId: string,
    request: SubmitAnswerRequest,
  ): Promise<Interaction> => {
    const { data } = await http.post<Interaction>(
      `/api/scenarios/${scenarioId}/answer`,
      request,
    )
    return data
  },

  getInteractions: async (scenarioId: string): Promise<ScenarioInteractionsResponse> => {
    const { data } = await http.get<ScenarioInteractionsResponse>(
      `/api/scenarios/${scenarioId}/interactions`,
    )
    return data
  },
}

// ── Health API ────────────────────────────────────────────────────────────────
export const healthApi = {
  check: async (): Promise<{ status: string; version: string }> => {
    const { data } = await http.get('/api/health')
    return data
  },
}
