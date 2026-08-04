import axios from 'axios'
import { getRefreshToken, authHeader } from './authToken'

// Backend mounts auth routes at "/api/auth/*" (baked into the router prefix, not
// stripped by the Vite dev proxy) — use the absolute backend URL like the other
// "/api/..."-prefixed clients (newsApi.ts, analytics.ts, assistant.ts).
const api = axios.create({ baseURL: 'http://localhost:8000/api/auth', headers: { 'Content-Type': 'application/json' } })

export interface AuthUser {
  id: string
  email: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
  last_login?: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export const authApi = {
  register: (email: string, password: string): Promise<{ user_id: string; email: string; role: string }> =>
    api.post('/register', { email, password }).then(r => r.data),

  login: (email: string, password: string): Promise<TokenResponse> =>
    api.post<TokenResponse>('/login', { email, password }).then(r => r.data),

  logout: (): Promise<{ status: string }> =>
    api.post('/logout', {}, { headers: authHeader() }).then(r => r.data).catch(() => ({ status: 'ignored' })),

  refresh: (): Promise<{ access_token: string; token_type: string }> => {
    const refreshToken = getRefreshToken()
    return api.post('/refresh', { refresh_token: refreshToken }).then(r => r.data)
  },

  getMe: (): Promise<AuthUser> =>
    api.get<AuthUser>('/me', { headers: authHeader() }).then(r => r.data),

  changePassword: (currentPassword: string, newPassword: string): Promise<{ status: string }> =>
    api.post('/change-password', { current_password: currentPassword, new_password: newPassword }, { headers: authHeader() }).then(r => r.data),

  listUsers: (): Promise<AuthUser[]> =>
    api.get<AuthUser[]>('/users', { headers: authHeader() }).then(r => r.data),

  forgotPassword: (email: string): Promise<{ status: string }> =>
    api.post('/forgot-password', { email }).then(r => r.data),

  resetPassword: (token: string, newPassword: string): Promise<{ status: string }> =>
    api.post('/reset-password', { token, new_password: newPassword }).then(r => r.data),
}
