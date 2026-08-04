// Centralized token storage — read fresh on every request so all API clients
// (axios instances created at module-load time, raw fetch calls, WebSocket URLs)
// always see the latest token without needing to be re-created after login.

const ACCESS_TOKEN_KEY = 'ragenie_access_token'
const REFRESH_TOKEN_KEY = 'ragenie_refresh_token'

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(accessToken: string, refreshToken?: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  }
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function authHeader(): Record<string, string> {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// Fired by API clients on a 401 response; AuthContext listens for this and logs
// the user out without each client needing a direct React context reference.
export const AUTH_EXPIRED_EVENT = 'ragenie:auth-expired'

export function notifyAuthExpired(): void {
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
}
