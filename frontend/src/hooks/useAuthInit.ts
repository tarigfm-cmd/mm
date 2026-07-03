import { useEffect } from 'react'
import { authApi, getRefreshToken, setStoredRefreshToken, clearStoredRefreshToken } from '@/services/api'
import { useAppStore } from '@/store/appStore'

export function useAuthInit() {
  const { setCurrentUser, setAccessToken, setAuthInitialized } = useAppStore()

  useEffect(() => {
    const init = async () => {
      const refreshToken = getRefreshToken()

      if (!refreshToken) {
        setAuthInitialized(true)
        return
      }

      try {
        const tokens = await authApi.refresh(refreshToken)
        setAccessToken(tokens.access_token)
        setStoredRefreshToken(tokens.refresh_token)

        const user = await authApi.me()
        setCurrentUser(user)
      } catch {
        clearStoredRefreshToken()
      } finally {
        setAuthInitialized(true)
      }
    }

    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}
