import { useState, useEffect, FormEvent } from 'react'
import { Mail, Lock, LogIn, UserPlus, Loader2, Sparkles, KeyRound, ArrowLeft, CheckCircle2 } from 'lucide-react'
import GenieLogo from '../GenieLogo'
import { useAuth } from '../../contexts/AuthContext'
import { useTheme } from '../../contexts/ThemeContext'
import { useToast } from '../../contexts/ToastContext'
import { authApi } from '../../api/authApi'

type Mode = 'login' | 'register' | 'forgot' | 'reset'

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [resetToken, setResetToken] = useState('')
  const [forgotSent, setForgotSent] = useState(false)
  const { login, register } = useAuth()
  const { theme } = useTheme()
  const toast = useToast()

  // A password-reset link (?token=...) drops the user straight into reset mode.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')
    if (token) {
      setResetToken(token)
      setMode('reset')
    }
  }, [])

  const switchMode = (next: Mode) => {
    setMode(next)
    setForgotSent(false)
    setPassword('')
    setConfirmPassword('')
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    if (mode === 'forgot') {
      if (!email.trim()) {
        toast('Please enter your email.', 'error')
        return
      }
      setSubmitting(true)
      try {
        await authApi.forgotPassword(email.trim())
        setForgotSent(true)
      } catch {
        // Backend intentionally returns 200 even for unknown emails; any error here is unexpected.
        toast('Something went wrong. Please try again.', 'error')
      } finally {
        setSubmitting(false)
      }
      return
    }

    if (mode === 'reset') {
      if (!password || password.length < 8) {
        toast('Password must be at least 8 characters.', 'error')
        return
      }
      if (password !== confirmPassword) {
        toast('Passwords do not match.', 'error')
        return
      }
      setSubmitting(true)
      try {
        await authApi.resetPassword(resetToken, password)
        toast('Password reset — please log in.', 'success')
        window.history.replaceState({}, '', window.location.pathname)
        switchMode('login')
      } catch (err: any) {
        toast(err?.response?.data?.detail || 'Reset link is invalid or expired.', 'error')
      } finally {
        setSubmitting(false)
      }
      return
    }

    if (!email.trim() || !password) {
      toast('Please enter both email and password.', 'error')
      return
    }
    if (mode === 'register' && password !== confirmPassword) {
      toast('Passwords do not match.', 'error')
      return
    }
    if (mode === 'register' && password.length < 8) {
      toast('Password must be at least 8 characters.', 'error')
      return
    }

    setSubmitting(true)
    try {
      if (mode === 'login') {
        await login(email.trim(), password)
        toast('Welcome back!', 'success')
      } else {
        await register(email.trim(), password)
        toast('Account created — welcome to RAGenie!', 'success')
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || (mode === 'login' ? 'Invalid email or password' : 'Registration failed')
      toast(detail, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={`min-h-screen w-full flex items-center justify-center transition-colors duration-300 ${
      theme === 'dark'
        ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900'
        : 'bg-gradient-to-br from-gray-50 via-blue-50 to-gray-50'
    }`}>
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage: theme === 'dark'
            ? `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
            : `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='0.02'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
        }}
      />

      <div className={`relative z-10 w-full max-w-md mx-4 backdrop-blur-2xl border rounded-2xl shadow-2xl p-8 transition-colors ${
        theme === 'dark' ? 'bg-slate-900/80 border-slate-700/50' : 'bg-white/90 border-gray-200'
      }`}>
        <div className="flex flex-col items-center mb-6">
          <GenieLogo size={56} />
          <h1 className={`mt-3 text-2xl font-semibold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
            RAGenie
          </h1>
          <p className={`text-xs flex items-center gap-1 font-medium mt-1 ${
            theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
          }`}>
            <Sparkles className="w-3 h-3" />
            AI Knowledge Assistant
          </p>
        </div>

        {/* Mode toggle (login/register) or back-link (forgot/reset) */}
        {(mode === 'login' || mode === 'register') ? (
          <div className={`flex rounded-xl p-1 mb-6 ${theme === 'dark' ? 'bg-slate-800' : 'bg-gray-100'}`}>
            <button
              type="button"
              onClick={() => switchMode('login')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all ${
                mode === 'login'
                  ? theme === 'dark' ? 'bg-blue-600 text-white' : 'bg-blue-500 text-white'
                  : theme === 'dark' ? 'text-slate-400 hover:text-slate-200' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <LogIn className="w-4 h-4" /> Login
            </button>
            <button
              type="button"
              onClick={() => switchMode('register')}
              className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-all ${
                mode === 'register'
                  ? theme === 'dark' ? 'bg-blue-600 text-white' : 'bg-blue-500 text-white'
                  : theme === 'dark' ? 'text-slate-400 hover:text-slate-200' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <UserPlus className="w-4 h-4" /> Register
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 mb-6">
            <button
              type="button"
              onClick={() => switchMode('login')}
              className={`flex items-center gap-1.5 text-sm font-medium ${theme === 'dark' ? 'text-slate-400 hover:text-slate-200' : 'text-slate-600 hover:text-slate-900'}`}
            >
              <ArrowLeft className="w-4 h-4" /> Back to login
            </button>
            <span className={`text-sm font-semibold ml-1 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
              {mode === 'forgot' ? '· Forgot Password' : '· Reset Password'}
            </span>
          </div>
        )}

        {mode === 'forgot' && forgotSent ? (
          <div className="text-center py-6">
            <CheckCircle2 className={`w-10 h-10 mx-auto mb-3 ${theme === 'dark' ? 'text-emerald-400' : 'text-emerald-500'}`} />
            <p className={`text-sm ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'}`}>
              If <span className="font-medium">{email.trim()}</span> is registered, a password reset link has been sent.
            </p>
            <button
              type="button"
              onClick={() => switchMode('login')}
              className={`mt-4 text-sm font-medium ${theme === 'dark' ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'}`}
            >
              Back to login
            </button>
          </div>
        ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {mode !== 'reset' && (
            <div>
              <label className={`block text-xs font-medium mb-1.5 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>
                Email
              </label>
              <div className={`flex items-center gap-2 rounded-xl border px-3 py-2.5 transition-colors ${
                theme === 'dark' ? 'bg-slate-800/50 border-slate-700 focus-within:border-blue-500' : 'bg-gray-50 border-gray-200 focus-within:border-blue-400'
              }`}>
                <Mail className={`w-4 h-4 flex-shrink-0 ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  className={`flex-1 bg-transparent outline-none text-sm ${theme === 'dark' ? 'text-white placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'}`}
                />
              </div>
            </div>
          )}

          {mode !== 'forgot' && (
            <div>
              <label className={`block text-xs font-medium mb-1.5 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>
                {mode === 'reset' ? 'New Password' : 'Password'}
              </label>
              <div className={`flex items-center gap-2 rounded-xl border px-3 py-2.5 transition-colors ${
                theme === 'dark' ? 'bg-slate-800/50 border-slate-700 focus-within:border-blue-500' : 'bg-gray-50 border-gray-200 focus-within:border-blue-400'
              }`}>
                <Lock className={`w-4 h-4 flex-shrink-0 ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder={mode === 'register' || mode === 'reset' ? 'Minimum 8 characters' : '••••••••'}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  className={`flex-1 bg-transparent outline-none text-sm ${theme === 'dark' ? 'text-white placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'}`}
                />
              </div>
              {mode === 'login' && (
                <button
                  type="button"
                  onClick={() => switchMode('forgot')}
                  className={`mt-1.5 text-xs font-medium ${theme === 'dark' ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'}`}
                >
                  Forgot password?
                </button>
              )}
            </div>
          )}

          {(mode === 'register' || mode === 'reset') && (
            <div>
              <label className={`block text-xs font-medium mb-1.5 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>
                Confirm Password
              </label>
              <div className={`flex items-center gap-2 rounded-xl border px-3 py-2.5 transition-colors ${
                theme === 'dark' ? 'bg-slate-800/50 border-slate-700 focus-within:border-blue-500' : 'bg-gray-50 border-gray-200 focus-within:border-blue-400'
              }`}>
                <Lock className={`w-4 h-4 flex-shrink-0 ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter your password"
                  autoComplete="new-password"
                  className={`flex-1 bg-transparent outline-none text-sm ${theme === 'dark' ? 'text-white placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'}`}
                />
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-xl font-medium transition-all disabled:opacity-60 ${
              theme === 'dark' ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'bg-blue-500 hover:bg-blue-600 text-white'
            }`}
          >
            {submitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : mode === 'login' ? (
              <LogIn className="w-4 h-4" />
            ) : mode === 'register' ? (
              <UserPlus className="w-4 h-4" />
            ) : (
              <KeyRound className="w-4 h-4" />
            )}
            {submitting
              ? 'Please wait…'
              : mode === 'login' ? 'Log In'
              : mode === 'register' ? 'Create Account'
              : mode === 'forgot' ? 'Send Reset Link'
              : 'Reset Password'}
          </button>
        </form>
        )}

        {(mode === 'login' || mode === 'register') && (
        <p className={`text-xs text-center mt-6 ${theme === 'dark' ? 'text-slate-500' : 'text-slate-500'}`}>
          {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
          <button
            type="button"
            onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
            className={`font-medium ${theme === 'dark' ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'}`}
          >
            {mode === 'login' ? 'Register' : 'Log in'}
          </button>
        </p>
        )}
      </div>
    </div>
  )
}
