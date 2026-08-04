# Spec: frontend-auth-ui

## Purpose

Add a Login/Register page and an `AuthContext` so the React frontend requires an authenticated session before rendering the main app, matching the existing visual language (Tailwind, `ThemeContext` dark/light mode, `ToastContext` feedback).

## Modules

- `frontend/src/contexts/AuthContext.tsx` (new)
- `frontend/src/api/authApi.ts` (new)
- `frontend/src/components/auth/LoginPage.tsx` (new)
- `frontend/src/App.tsx` (modified — route gating)
- `frontend/src/main.tsx` (modified — wrap with `AuthProvider`)
- Existing API client files under `frontend/src/api/` (modified — attach auth header)

## Public Interface

```typescript
// AuthContext.tsx
interface AuthUser {
  id: string;
  email: string;
  role: "admin" | "user";
}

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refreshAccessToken: () => Promise<string | null>;
}

// authApi.ts
export function login(email: string, password: string): Promise<{ access_token: string; refresh_token: string }>;
export function register(email: string, password: string): Promise<{ user_id: string; email: string; role: string }>;
export function getMe(token: string): Promise<AuthUser>;
export function refresh(refreshToken: string): Promise<{ access_token: string }>;
```

## Behavior

- Tokens persisted in `localStorage` under `ragenie_access_token` / `ragenie_refresh_token`.
- On app load, `AuthProvider` attempts to hydrate `user` via `getMe()` using the stored access token; on failure, attempts `refresh()`; on failure, clears tokens and treats the session as unauthenticated.
- A shared axios instance (or an interceptor applied to each existing API client under `frontend/src/api/`) attaches `Authorization: Bearer <accessToken>` to every request.
- On any `401` response, the interceptor attempts exactly one silent `refresh()`; if that also fails, calls `logout()` and the app re-renders `LoginPage`.
- `App.tsx`: while `isLoading`, show a lightweight loading state (reuse `SplashScreen.tsx` if appropriate); once resolved, render `LoginPage` if `!isAuthenticated`, else the existing app shell.
- `LoginPage` toggles between Login and Register forms; on submit, calls `AuthContext.login`/`register`; displays field-level and top-level errors via `ToastContext`.
- Successful login/register transitions directly into the app shell (no separate "verify email" step in v1).
- `logout()` clears localStorage tokens and resets context state; `Sidebar` (or a header area) exposes a visible "Logout" action plus the current user's email.

## Validation Rules

- Client-side email format + password length checks before submitting (defense in depth; server is authoritative).
- Register form calls the existing `/api/auth/register` endpoint; first-ever registration is auto-granted admin server-side (existing behavior in `src/api/auth_routes.py:44-57`) — the frontend does not need special-case logic for this, it just reflects whatever role `getMe()` returns.

## Error Behavior

- Invalid credentials → toast "Invalid email or password" (mapped from `401` on `/login`).
- Duplicate email on register → toast "Email already registered" (mapped from `409`).
- Network/server errors → generic toast, form remains editable.

## Tests / Verification

- Manual: fresh browser session with no tokens → only `LoginPage` renders.
- Manual: successful login persists tokens across a page reload (still authenticated after refresh).
- Manual: expired access token + valid refresh token → seamless silent refresh, no visible interruption.
- Manual: expired/invalid refresh token → forced back to `LoginPage`.
