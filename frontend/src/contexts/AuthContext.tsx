import { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react'
import { authApi, AuthUser } from '../api/authApi'
import { getAccessToken, getRefreshToken, setTokens, clearTokens, AUTH_EXPIRED_EVENT } from '../api/authToken'

interface AuthContextType {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshAccessToken: () => Promise<string | null>
  clearError: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const hydrate = useCallback(async () => {
    const token = getAccessToken()
    if (!token) {
      setIsLoading(false)
      return
    }
    try {
      const me = await authApi.getMe()
      setUser(me)
    } catch {
      // Access token invalid/expired — try a silent refresh once
      try {
        if (getRefreshToken()) {
          const { access_token } = await authApi.refresh()
          setTokens(access_token)
          const me = await authApi.getMe()
          setUser(me)
        } else {
          clearTokens()
        }
      } catch {
        clearTokens()
        setUser(null)
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    hydrate()
  }, [hydrate])

  const login = useCallback(async (email: string, password: string) => {
    setError(null)
    try {
      const tokens = await authApi.login(email, password)
      setTokens(tokens.access_token, tokens.refresh_token)
      const me = await authApi.getMe()
      setUser(me)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Invalid email or password'
      setError(detail)
      throw err
    }
  }, [])

  const register = useCallback(async (email: string, password: string) => {
    setError(null)
    try {
      await authApi.register(email, password)
      await login(email, password)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || 'Registration failed'
      setError(detail)
      throw err
    }
  }, [login])

  const logout = useCallback(() => {
    authApi.logout()
    clearTokens()
    setUser(null)
  }, [])

  // Any API client can dispatch this event on a 401 to force a logout without
  // needing a direct reference to this context (see api/authToken.ts).
  useEffect(() => {
    const handler = () => logout()
    window.addEventListener(AUTH_EXPIRED_EVENT, handler)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handler)
  }, [logout])

  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    try {
      if (!getRefreshToken()) return null
      const { access_token } = await authApi.refresh()
      setTokens(access_token)
      return access_token
    } catch {
      clearTokens()
      setUser(null)
      return null
    }
  }, [])

  const clearError = useCallback(() => setError(null), [])

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        error,
        login,
        register,
        logout,
        refreshAccessToken,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
