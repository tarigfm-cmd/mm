/**
 * Billing API client — subscription plans, usage, admin assignment.
 * Reuses the same JWT refresh interceptor pattern as other API clients.
 */
import axios from 'axios'
import { useAppStore } from '@/store/appStore'
import { getRefreshToken, setStoredRefreshToken } from '@/services/api'
import type {
  MonthlyUsageResponse,
  SubscriptionPlanRead,
  UserSubscriptionRead,
  UserSubscriptionWithFallback,
} from '@/types/billing'

const BASE_URL = ((import.meta as unknown) as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL ?? ''

const billingHttp = axios.create({
  baseURL: BASE_URL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})
const billingAuthHttp = axios.create({ baseURL: BASE_URL, timeout: 15_000 })

billingHttp.interceptors.request.use((config) => {
  const { accessToken } = useAppStore.getState()
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

let _refreshing = false
let _pending: Array<(token: string) => void> = []

billingHttp.interceptors.response.use(
  (r) => r,
  async (err) => {
    const original = err.config as typeof err.config & { _retry?: boolean }
    const httpStatus = err.response?.status
    if (
      httpStatus === 401 &&
      !original._retry &&
      original.url &&
      !original.url.includes('/api/auth/')
    ) {
      original._retry = true
      if (_refreshing) {
        return new Promise<string>((res) => _pending.push(res)).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return billingHttp(original)
        })
      }
      _refreshing = true
      try {
        const rt = getRefreshToken()
        if (!rt) throw new Error('no refresh token')
        const { data } = await billingAuthHttp.post('/api/auth/refresh', {
          refresh_token: rt,
        })
        useAppStore.getState().setAccessToken(data.access_token)
        setStoredRefreshToken(data.refresh_token)
        _pending.forEach((cb) => cb(data.access_token))
        _pending = []
        original.headers.Authorization = `Bearer ${data.access_token}`
        return billingHttp(original)
      } catch {
        useAppStore.getState().clearAuth()
        window.location.href = '/login'
        return Promise.reject(err)
      } finally {
        _refreshing = false
      }
    }
    return Promise.reject(err)
  },
)

export const billingApi = {
  getPlans: async (): Promise<SubscriptionPlanRead[]> => {
    const { data } = await billingHttp.get<SubscriptionPlanRead[]>('/api/billing/plans')
    return data
  },

  getMySubscription: async (): Promise<UserSubscriptionWithFallback> => {
    const { data } = await billingHttp.get<UserSubscriptionWithFallback>(
      '/api/billing/me/subscription',
    )
    return data
  },

  getMyUsage: async (): Promise<MonthlyUsageResponse> => {
    const { data } = await billingHttp.get<MonthlyUsageResponse>('/api/billing/me/usage')
    return data
  },

  adminAssignPlan: async (
    userId: string,
    planCode: string,
    subStatus = 'active',
  ): Promise<UserSubscriptionRead> => {
    const { data } = await billingHttp.post<UserSubscriptionRead>(
      `/api/billing/admin/users/${userId}/subscription`,
      { plan_code: planCode, status: subStatus },
    )
    return data
  },
}
