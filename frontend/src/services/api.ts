import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import toast from 'react-hot-toast'
import { useAppStore } from '@/store/appStore'
import type {
  AddMemberRequest,
  CreateOrgRequest,
  GenerateScenarioRequest,
  Interaction,
  LoginRequest,
  MaterialDetail,
  MaterialListResponse,
  Member,
  Organization,
  OrgWithRole,
  RegisterRequest,
  Scenario,
  ScenarioInteractionsResponse,
  ScenarioListResponse,
  SubmitAnswerRequest,
  SystemRole,
  TokenResponse,
  UserRead,
} from '@/types'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const BASE_URL = (import.meta as any).env?.VITE_API_URL ?? ''

// ── Refresh token storage (localStorage) ─────────────────────────────────────

const RT_KEY = 'pharmlearn_rt'

export function getRefreshToken(): string | null {
  return localStorage.getItem(RT_KEY)
}

export function setStoredRefreshToken(token: string): void {
  localStorage.setItem(RT_KEY, token)
}

export function clearStoredRefreshToken(): void {
  localStorage.removeItem(RT_KEY)
}

// ── Axios instance ────────────────────────────────────────────────────────────

const http: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

// Separate instance for token refresh — no interceptors to avoid loops
const authHttp = axios.create({ baseURL: BASE_URL, timeout: 30_000 })

// ── Request interceptor: attach access token + session ID ─────────────────────

http.interceptors.request.use((config) => {
  const { accessToken } = useAppStore.getState()
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  config.headers['X-Session-Id'] = getOrCreateSessionId()
  return config
})

// ── Response interceptor: silent token refresh on 401 ────────────────────────

let _isRefreshing = false
let _pendingCallbacks: Array<(token: string) => void> = []

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail: string }>) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    const status = error.response?.status

    // Attempt silent refresh on 401, but not for auth endpoints or retried requests
    if (
      status === 401 &&
      !original._retry &&
      original.url &&
      !original.url.includes('/api/auth/')
    ) {
      original._retry = true

      if (_isRefreshing) {
        return new Promise<string>((resolve) => _pendingCallbacks.push(resolve)).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return http(original)
        })
      }

      _isRefreshing = true
      try {
        const rt = getRefreshToken()
        if (!rt) throw new Error('no refresh token')

        const { data } = await authHttp.post<TokenResponse>('/api/auth/refresh', {
          refresh_token: rt,
        })

        useAppStore.getState().setAccessToken(data.access_token)
        setStoredRefreshToken(data.refresh_token)

        _pendingCallbacks.forEach((cb) => cb(data.access_token))
        _pendingCallbacks = []

        original.headers.Authorization = `Bearer ${data.access_token}`
        return http(original)
      } catch {
        _pendingCallbacks = []
        useAppStore.getState().clearAuth()
        clearStoredRefreshToken()
        window.location.replace('/login')
        return Promise.reject(error)
      } finally {
        _isRefreshing = false
      }
    }

    // Surface errors as toasts (skip 401 and 404)
    if (status !== 401 && status !== 404) {
      const message = error.response?.data?.detail ?? error.message ?? 'An unexpected error occurred.'
      const detail = typeof message === 'string' ? message : JSON.stringify(message)
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

// ── Auth API ──────────────────────────────────────────────────────────────────

export const authApi = {
  register: async (data: RegisterRequest): Promise<UserRead> => {
    const { data: user } = await http.post<UserRead>('/api/auth/register', data)
    return user
  },

  login: async (credentials: LoginRequest): Promise<TokenResponse> => {
    const { data } = await http.post<TokenResponse>('/api/auth/login', credentials)
    useAppStore.getState().setAccessToken(data.access_token)
    setStoredRefreshToken(data.refresh_token)
    return data
  },

  refresh: async (refreshToken: string): Promise<TokenResponse> => {
    const { data } = await authHttp.post<TokenResponse>('/api/auth/refresh', {
      refresh_token: refreshToken,
    })
    return data
  },

  me: async (): Promise<UserRead> => {
    const { data } = await http.get<UserRead>('/api/auth/me')
    return data
  },

  logout: async (): Promise<void> => {
    const rt = getRefreshToken()
    if (rt) {
      try {
        await http.post('/api/auth/logout', { refresh_token: rt })
      } catch {
        // best-effort
      }
    }
    useAppStore.getState().clearAuth()
    clearStoredRefreshToken()
  },
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

// ── Organizations API ─────────────────────────────────────────────────────────

export const orgsApi = {
  list: async (): Promise<OrgWithRole[]> => {
    const { data } = await http.get<OrgWithRole[]>('/api/orgs')
    return data
  },

  create: async (body: CreateOrgRequest): Promise<Organization> => {
    const { data } = await http.post<Organization>('/api/orgs', body)
    return data
  },

  get: async (slug: string): Promise<Organization> => {
    const { data } = await http.get<Organization>(`/api/orgs/${slug}`)
    return data
  },

  update: async (slug: string, body: CreateOrgRequest): Promise<Organization> => {
    const { data } = await http.patch<Organization>(`/api/orgs/${slug}`, body)
    return data
  },

  listMembers: async (slug: string): Promise<Member[]> => {
    const { data } = await http.get<Member[]>(`/api/orgs/${slug}/members`)
    return data
  },

  addMember: async (slug: string, body: AddMemberRequest): Promise<Member> => {
    const { data } = await http.post<Member>(`/api/orgs/${slug}/members`, body)
    return data
  },

  updateMemberRole: async (slug: string, userId: string, roleName: string): Promise<Member> => {
    const { data } = await http.patch<Member>(`/api/orgs/${slug}/members/${userId}`, {
      role_name: roleName,
    })
    return data
  },

  removeMember: async (slug: string, userId: string): Promise<void> => {
    await http.delete(`/api/orgs/${slug}/members/${userId}`)
  },
}

export const rolesApi = {
  list: async (): Promise<SystemRole[]> => {
    const { data } = await http.get<SystemRole[]>('/api/roles')
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
