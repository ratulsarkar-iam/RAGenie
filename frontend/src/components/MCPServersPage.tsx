import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Plus, Trash2, RefreshCw, Play, Square, Wrench, Upload,
  X, ChevronDown, ChevronUp, Loader2, CheckCircle2,
  AlertCircle, FlaskConical, Copy, Check,
  MessageSquare, Send, Server, Bot, RotateCcw,
  FolderOpen, FolderPlus, KeyRound, LogIn, Newspaper,
} from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import {
  mcpApi, ServerWithStatus, ServerCreateRequest, ToolDefinition,
  Transport, TestResult, MCPChatMessage, ToolCallTrace, PathSuggestion,
} from '../api/mcpClient'

// ── helpers ──────────────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, { dot: string; label: string; bg: string }> = {
  connected:    { dot: 'text-emerald-400', label: 'Connected',    bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  connecting:   { dot: 'text-yellow-400 animate-pulse', label: 'Connecting…', bg: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  error:        { dot: 'text-red-400',     label: 'Error',        bg: 'bg-red-500/10 text-red-400 border-red-500/20' },
  disconnected: { dot: 'text-slate-500',   label: 'Disconnected', bg: 'bg-slate-500/10 text-slate-400 border-slate-500/20' },
}

const TRANSPORT_BADGE: Record<Transport, string> = {
  http:  'bg-blue-500/10 text-blue-400 border-blue-500/20',
  sse:   'bg-purple-500/10 text-purple-400 border-purple-500/20',
  stdio: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
}

const BLANK_FORM: ServerCreateRequest = {
  name: '', transport: 'http', enabled: true, connect_now: true,
  url: '', command: '', args: [], headers: {}, env: {},
}

function kvToStr(obj?: Record<string, string>) {
  if (!obj) return ''
  return Object.entries(obj).map(([k, v]) => `${k}=${v}`).join('\n')
}
function strToKv(s: string): Record<string, string> | undefined {
  const out: Record<string, string> = {}
  for (const line of s.split('\n')) {
    const eq = line.indexOf('=')
    if (eq < 1) continue
    out[line.slice(0, eq).trim()] = line.slice(eq + 1).trim()
  }
  return Object.keys(out).length ? out : undefined
}

// ── StatusBadge ───────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.disconnected
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${s.bg}`}>
      <span className={`w-1.5 h-1.5 rounded-full bg-current ${s.dot.includes('pulse') ? 'animate-pulse' : ''}`} />
      {s.label}
    </span>
  )
}

// ── ToolsPanel ────────────────────────────────────────────────────────────────
function ToolsPanel({ tools }: { tools: ToolDefinition[] }) {
  const { theme } = useTheme()
  if (!tools.length) return <p className="text-slate-500 text-sm py-2">No tools available.</p>
  return (
    <div className="space-y-2 mt-2">
      {tools.map(t => (
        <div key={t.tool_id} className={`p-3 rounded-lg border text-sm ${
          theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-gray-50 border-gray-200'
        }`}>
          <div className="flex items-center gap-2">
            <code className={`font-mono font-semibold text-xs px-2 py-0.5 rounded ${
              theme === 'dark' ? 'bg-blue-900/40 text-blue-300' : 'bg-blue-100 text-blue-700'
            }`}>{t.server_name}/{t.name}</code>
          </div>
          <p className={`mt-1 text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>{t.description}</p>
        </div>
      ))}
    </div>
  )
}

// ── ServerCard ────────────────────────────────────────────────────────────────
function ServerCard({
  item, onConnect, onDisconnect, onDelete, onTest, onEdit, onQuickLogin,
}: {
  item: ServerWithStatus
  onConnect: () => void
  onDisconnect: () => void
  onDelete: () => void
  onTest: () => void
  onEdit: () => void
  onQuickLogin?: (serverId: string) => void
}) {
  const { theme } = useTheme()
  const [showTools, setShowTools] = useState(false)
  const [busy, setBusy] = useState(false)
  const { config, status, tools } = item
  const isConnected = status.status === 'connected'
  const isLoggedIn = status.session_meta?.logged_in === true
  const loggedInAt = status.session_meta?.logged_in_at as string | undefined
  const hasLoginTool = tools.some(t => t.name === 'login')

  const wrap = async (fn: () => void | Promise<void>) => { setBusy(true); try { await fn() } finally { setBusy(false) } }

  return (
    <div className={`rounded-2xl border backdrop-blur-xl p-5 flex flex-col gap-4 transition-all ${
      theme === 'dark'
        ? 'bg-slate-800/60 border-slate-700/60 hover:border-slate-600'
        : 'bg-white/80 border-gray-200 hover:border-gray-300 shadow-sm'
    }`}>
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className={`font-semibold truncate ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
              {config.name}
            </h3>
            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${TRANSPORT_BADGE[config.transport]}`}>
              {config.transport.toUpperCase()}
            </span>
            {!config.enabled && (
              <span className="text-xs px-2 py-0.5 rounded-full border bg-slate-500/10 text-slate-400 border-slate-500/20">disabled</span>
            )}
          </div>
          <p className={`text-xs mt-1 truncate ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>
            {config.url || config.command || '—'}
          </p>
        </div>
        <StatusBadge status={status.status} />
      </div>

      {/* Meta row */}
      <div className={`flex flex-wrap gap-4 text-xs ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>
        <span><span className="font-medium">{status.tool_count}</span> tool{status.tool_count !== 1 ? 's' : ''}</span>
        {status.last_connected_at && (
          <span>Last: {new Date(status.last_connected_at).toLocaleTimeString()}</span>
        )}
        {isLoggedIn ? (
          <span className="flex items-center gap-1 text-emerald-400 font-medium" title={loggedInAt ? `Logged in at ${loggedInAt}` : undefined}>
            <KeyRound className="w-3 h-3" /> Authenticated{loggedInAt ? ` · ${loggedInAt}` : ''}
          </span>
        ) : hasLoginTool && isConnected ? (
          <span className="flex items-center gap-1 text-amber-400">
            <KeyRound className="w-3 h-3" /> Login required
          </span>
        ) : null}
        {status.error_message && (
          <span className="text-red-400 truncate max-w-[200px]" title={status.error_message}>
            {status.error_message}
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        {isConnected ? (
          <button onClick={() => wrap(onDisconnect)} disabled={busy}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-all disabled:opacity-50">
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Square className="w-3 h-3" />}
            Disconnect
          </button>
        ) : (
          <button onClick={() => wrap(onConnect)} disabled={busy || !config.enabled}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-all disabled:opacity-50">
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
            Connect
          </button>
        )}
        {hasLoginTool && isConnected && !isLoggedIn && onQuickLogin && (
          <button onClick={() => onQuickLogin(config.id)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-all">
            <LogIn className="w-3 h-3" /> Login
          </button>
        )}
        <button onClick={onTest}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
            theme === 'dark' ? 'bg-slate-700 text-slate-300 border-slate-600 hover:bg-slate-600' : 'bg-gray-100 text-slate-600 border-gray-200 hover:bg-gray-200'
          }`}>
          <FlaskConical className="w-3 h-3" /> Test
        </button>
        <button onClick={onEdit}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
            theme === 'dark' ? 'bg-slate-700 text-slate-300 border-slate-600 hover:bg-slate-600' : 'bg-gray-100 text-slate-600 border-gray-200 hover:bg-gray-200'
          }`}>
          Edit
        </button>
        <button onClick={onDelete}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-all">
          <Trash2 className="w-3 h-3" />
        </button>
        {isConnected && tools.length > 0 && (
          <button onClick={() => setShowTools(v => !v)}
            className={`ml-auto flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
              theme === 'dark' ? 'bg-slate-700 text-slate-300 border-slate-600 hover:bg-slate-600' : 'bg-gray-100 text-slate-600 border-gray-200 hover:bg-gray-200'
            }`}>
            <Wrench className="w-3 h-3" />
            Tools
            {showTools ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
        )}
      </div>

      {showTools && <ToolsPanel tools={tools} />}
    </div>
  )
}

// ── FilesystemDirEditor ───────────────────────────────────────────────────────
// Shown instead of the plain args textarea when the stdio command uses a
// server-filesystem package. Splits the args into a fixed prefix (e.g.
// "-y @modelcontextprotocol/server-filesystem") and an editable list of
// allowed directory paths, with OS-aware suggestions from the backend.
function FilesystemDirEditor({
  argsStr, onChange,
}: {
  argsStr: string
  onChange: (next: string) => void
}) {
  const { theme } = useTheme()
  const [suggestions, setSuggestions] = useState<PathSuggestion[]>([])
  const [manual, setManual] = useState('')

  useEffect(() => {
    mcpApi.pathSuggestions().then(setSuggestions).catch(() => {})
  }, [])

  const lines = argsStr.split('\n').map(s => s.trim()).filter(Boolean)
  const splitIdx = lines.findIndex(l => l.includes('server-filesystem'))
  const prefixLines = splitIdx >= 0 ? lines.slice(0, splitIdx + 1) : lines
  const dirLines   = splitIdx >= 0 ? lines.slice(splitIdx + 1) : []

  const rebuild = (dirs: string[]) =>
    onChange([...prefixLines, ...dirs].join('\n'))

  const addDir = (p: string) => {
    const t = p.trim()
    if (!t || dirLines.includes(t)) return
    rebuild([...dirLines, t])
    setManual('')
  }

  const removeDir = (p: string) =>
    rebuild(dirLines.filter(d => d !== p))

  const inputCls = `flex-1 px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all ${
    theme === 'dark' ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500' : 'bg-white border-gray-300 text-slate-900 placeholder-gray-400'
  }`
  const chipBase = `text-xs px-2 py-1 rounded-lg border font-medium transition-all cursor-pointer`
  const mutedText = theme === 'dark' ? 'text-slate-500' : 'text-slate-400'
  const cardCls = `p-3 rounded-xl border ${theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-gray-50 border-gray-200'}`

  return (
    <div className="space-y-3">
      {/* Fixed prefix — read-only display */}
      <div className={`${cardCls} font-mono text-xs ${mutedText}`}>
        <span className="font-semibold text-xs uppercase tracking-wide mr-2">Command args:</span>
        {prefixLines.join(' ')}
      </div>

      {/* Current allowed directories */}
      <div>
        <p className={`text-xs font-medium mb-2 flex items-center gap-1.5 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>
          <FolderOpen className="w-3.5 h-3.5" /> Allowed directories
        </p>
        {dirLines.length === 0 ? (
          <p className={`text-xs ${mutedText} italic`}>No directories allowed yet — add one below.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {dirLines.map(d => (
              <span key={d} className={`${chipBase} pr-1 flex items-center gap-1 ${
                theme === 'dark' ? 'bg-blue-900/30 text-blue-300 border-blue-700/50' : 'bg-blue-50 text-blue-700 border-blue-200'
              }`}>
                <span className="font-mono">{d}</span>
                <button onClick={() => removeDir(d)} className="ml-0.5 rounded hover:text-red-400 transition-colors">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Quick-add suggestions */}
      {suggestions.length > 0 && (
        <div>
          <p className={`text-xs font-medium mb-2 flex items-center gap-1.5 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>
            <FolderPlus className="w-3.5 h-3.5" /> Quick add
          </p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map(s => {
              const added = dirLines.includes(s.path)
              return (
                <button key={s.path}
                  onClick={() => addDir(s.path)}
                  disabled={added}
                  title={s.path}
                  className={`${chipBase} ${added
                    ? theme === 'dark' ? 'bg-slate-700 text-slate-500 border-slate-600 cursor-default' : 'bg-gray-100 text-gray-400 border-gray-200 cursor-default'
                    : theme === 'dark' ? 'bg-slate-700 text-slate-300 border-slate-600 hover:bg-slate-600 hover:text-white' : 'bg-white text-slate-600 border-gray-300 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300'
                  }`}>
                  {added ? <Check className="w-3 h-3 inline mr-1" /> : null}
                  {s.label}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Manual path input */}
      <div className="flex gap-2">
        <input
          className={inputCls}
          value={manual}
          onChange={e => setManual(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && addDir(manual)}
          placeholder="Type a custom path and press Enter…"
        />
        <button
          onClick={() => addDir(manual)}
          disabled={!manual.trim()}
          className="px-3 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 transition-all">
          Add
        </button>
      </div>
    </div>
  )
}

// ── ServerForm (Add / Edit modal) ─────────────────────────────────────────────
function ServerFormModal({
  initial, onSave, onClose,
}: {
  initial?: Partial<ServerCreateRequest> & { id?: string }
  onSave: (data: ServerCreateRequest, id?: string) => Promise<void>
  onClose: () => void
}) {
  const { theme } = useTheme()
  const [form, setForm] = useState<ServerCreateRequest>({ ...BLANK_FORM, ...initial })
  const [envStr, setEnvStr] = useState(kvToStr(initial?.env))
  const [headersStr, setHeadersStr] = useState(kvToStr(initial?.headers))
  const [argsStr, setArgsStr] = useState((initial?.args ?? []).join('\n'))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const set = (k: keyof ServerCreateRequest, v: any) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async () => {
    if (!form.name.trim()) { setError('Name is required'); return }
    if (form.transport === 'stdio' && !form.command?.trim()) { setError('Command is required for stdio'); return }
    if ((form.transport === 'sse' || form.transport === 'http') && !form.url?.trim()) { setError('URL is required for ' + form.transport); return }
    setSaving(true); setError('')
    try {
      const payload: ServerCreateRequest = {
        ...form,
        args: argsStr.split('\n').map(s => s.trim()).filter(Boolean),
        env: strToKv(envStr),
        headers: strToKv(headersStr),
      }
      await onSave(payload, (initial as any)?.id)
      onClose()
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Save failed')
    } finally { setSaving(false) }
  }

  const inputCls = `w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all ${
    theme === 'dark' ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500' : 'bg-white border-gray-300 text-slate-900 placeholder-gray-400'
  }`
  const labelCls = `block text-xs font-medium mb-1 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`
  const areaCls = `${inputCls} font-mono text-xs resize-none`

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className={`w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden ${theme === 'dark' ? 'bg-slate-900' : 'bg-white'}`}>
        <div className={`px-6 py-4 border-b flex items-center justify-between ${theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-gray-50 border-gray-200'}`}>
          <h2 className={`text-lg font-semibold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
            {(initial as any)?.id ? 'Edit Server' : 'Add MCP Server'}
          </h2>
          <button onClick={onClose} className={`p-1.5 rounded-lg transition-all ${theme === 'dark' ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-gray-200 text-slate-500'}`}>
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          {/* Name */}
          <div>
            <label className={labelCls}>Name *</label>
            <input className={inputCls} value={form.name} onChange={e => set('name', e.target.value)} placeholder="my-server" />
          </div>

          {/* Transport */}
          <div>
            <label className={labelCls}>Transport *</label>
            <div className="flex gap-2">
              {(['http', 'sse', 'stdio'] as Transport[]).map(t => (
                <button key={t} onClick={() => set('transport', t)}
                  className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-all ${
                    form.transport === t
                      ? 'bg-blue-600 text-white border-blue-600'
                      : theme === 'dark' ? 'bg-slate-700 text-slate-300 border-slate-600 hover:bg-slate-600' : 'bg-gray-100 text-slate-700 border-gray-200 hover:bg-gray-200'
                  }`}
                >{t.toUpperCase()}</button>
              ))}
            </div>
            <p className={`text-xs mt-1 ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>
              {form.transport === 'http' ? 'Modern streamable HTTP (recommended for public servers)' :
               form.transport === 'sse'  ? 'Legacy Server-Sent Events transport' :
                                           'Local subprocess via stdin/stdout'}
            </p>
          </div>

          {/* URL or command */}
          {form.transport !== 'stdio' ? (
            <div>
              <label className={labelCls}>URL *</label>
              <input className={inputCls} value={form.url ?? ''} onChange={e => set('url', e.target.value)} placeholder="https://example.com/mcp" />
            </div>
          ) : (
            <>
              <div>
                <label className={labelCls}>Command *</label>
                <input className={inputCls} value={form.command ?? ''} onChange={e => set('command', e.target.value)} placeholder="npx" />
              </div>
              <div>
                <label className={labelCls}>Arguments</label>
                {argsStr.includes('server-filesystem') ? (
                  <FilesystemDirEditor argsStr={argsStr} onChange={setArgsStr} />
                ) : (
                  <textarea className={areaCls} rows={3} value={argsStr} onChange={e => setArgsStr(e.target.value)}
                    placeholder={"-y\n@modelcontextprotocol/server-filesystem\n/tmp"} />
                )}
              </div>
              <div>
                <label className={labelCls}>Environment variables (KEY=VALUE, one per line)</label>
                <textarea className={areaCls} rows={3} value={envStr} onChange={e => setEnvStr(e.target.value)} placeholder="GITHUB_TOKEN=ghp_..." />
              </div>
            </>
          )}

          {/* Headers (HTTP/SSE) */}
          {form.transport !== 'stdio' && (
            <div>
              <label className={labelCls}>Auth headers (KEY=VALUE, one per line)</label>
              <textarea className={areaCls} rows={2} value={headersStr} onChange={e => setHeadersStr(e.target.value)} placeholder="Authorization=Bearer YOUR_TOKEN" />
            </div>
          )}

          {/* Options */}
          <div className="flex gap-6">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" checked={form.enabled} onChange={e => set('enabled', e.target.checked)}
                className="w-4 h-4 rounded accent-blue-500" />
              <span className={`text-sm ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'}`}>Enabled</span>
            </label>
            {!(initial as any)?.id && (
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input type="checkbox" checked={form.connect_now} onChange={e => set('connect_now', e.target.checked)}
                  className="w-4 h-4 rounded accent-blue-500" />
                <span className={`text-sm ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'}`}>Connect immediately</span>
              </label>
            )}
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>
        <div className={`px-6 py-4 border-t flex justify-end gap-3 ${theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-gray-50 border-gray-200'}`}>
          <button onClick={onClose} className={`px-4 py-2 rounded-lg text-sm font-medium border transition-all ${
            theme === 'dark' ? 'bg-slate-700 text-slate-300 border-slate-600 hover:bg-slate-600' : 'bg-white text-slate-700 border-gray-300 hover:bg-gray-50'
          }`}>Cancel</button>
          <button onClick={handleSubmit} disabled={saving}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-all disabled:opacity-60 flex items-center gap-2">
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            {(initial as any)?.id ? 'Save Changes' : 'Add Server'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── ImportModal ───────────────────────────────────────────────────────────────
function ImportModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { theme } = useTheme()
  const [json, setJson] = useState('')
  const [connectNow, setConnectNow] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<null | { created: number; updated: number; skipped: number }>(null)
  const [error, setError] = useState('')

  const handleImport = async () => {
    setError(''); setLoading(true)
    try {
      const parsed = JSON.parse(json)
      const servers = parsed.mcpServers ?? parsed
      const res = await mcpApi.import(servers, connectNow)
      setResult(res)
      onDone()
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Import failed')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className={`w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden ${theme === 'dark' ? 'bg-slate-900' : 'bg-white'}`}>
        <div className={`px-6 py-4 border-b flex items-center justify-between ${theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-gray-50 border-gray-200'}`}>
          <h2 className={`text-lg font-semibold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Import from Claude Desktop JSON</h2>
          <button onClick={onClose} className={`p-1.5 rounded-lg ${theme === 'dark' ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-gray-200 text-slate-500'}`}><X className="w-5 h-5" /></button>
        </div>
        <div className="p-6 space-y-4">
          <p className={`text-sm ${theme === 'dark' ? 'text-slate-400' : 'text-slate-600'}`}>
            Paste your <code className="font-mono">claude_desktop_config.json</code> or any JSON with an <code className="font-mono">mcpServers</code> key.
          </p>
          <textarea
            className={`w-full h-48 px-3 py-2 rounded-lg border text-xs font-mono focus:outline-none focus:ring-2 focus:ring-blue-500/50 resize-none ${
              theme === 'dark' ? 'bg-slate-800 border-slate-600 text-slate-200' : 'bg-gray-50 border-gray-300 text-slate-800'
            }`}
            value={json} onChange={e => setJson(e.target.value)}
            placeholder={'{\n  "mcpServers": {\n    "filesystem": {\n      "command": "npx",\n      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]\n    }\n  }\n}'}
          />
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input type="checkbox" checked={connectNow} onChange={e => setConnectNow(e.target.checked)} className="w-4 h-4 rounded accent-blue-500" />
            <span className={`text-sm ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'}`}>Connect servers after import</span>
          </label>
          {error && <p className="text-sm text-red-400">{error}</p>}
          {result && (
            <div className="flex gap-4 text-sm">
              <span className="text-emerald-400">+{result.created} created</span>
              <span className="text-blue-400">~{result.updated} updated</span>
              {result.skipped > 0 && <span className="text-slate-400">{result.skipped} skipped</span>}
            </div>
          )}
        </div>
        <div className={`px-6 py-4 border-t flex justify-end gap-3 ${theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-gray-50 border-gray-200'}`}>
          <button onClick={onClose} className={`px-4 py-2 rounded-lg text-sm font-medium border ${
            theme === 'dark' ? 'bg-slate-700 text-slate-300 border-slate-600 hover:bg-slate-600' : 'bg-white text-slate-700 border-gray-300 hover:bg-gray-50'
          }`}>{result ? 'Close' : 'Cancel'}</button>
          {!result && (
            <button onClick={handleImport} disabled={loading || !json.trim()}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60 flex items-center gap-2">
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              Import
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── TestResultModal ───────────────────────────────────────────────────────────
function TestResultModal({ result, name, onClose }: { result: TestResult; name: string; onClose: () => void }) {
  const { theme } = useTheme()
  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className={`w-full max-w-md rounded-2xl shadow-2xl overflow-hidden ${theme === 'dark' ? 'bg-slate-900' : 'bg-white'}`}>
        <div className={`px-6 py-4 border-b flex items-center justify-between ${theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-gray-50 border-gray-200'}`}>
          <h2 className={`text-lg font-semibold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Test — {name}</h2>
          <button onClick={onClose} className={`p-1.5 rounded-lg ${theme === 'dark' ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-gray-200 text-slate-500'}`}><X className="w-5 h-5" /></button>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-center gap-3">
            {result.success
              ? <CheckCircle2 className="w-8 h-8 text-emerald-400" />
              : <AlertCircle className="w-8 h-8 text-red-400" />}
            <div>
              <p className={`font-semibold ${result.success ? 'text-emerald-400' : 'text-red-400'}`}>
                {result.success ? 'Connection successful' : 'Connection failed'}
              </p>
              {result.latency_ms && <p className={`text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>{result.latency_ms}ms latency</p>}
            </div>
          </div>
          {result.error && <p className="text-sm text-red-400 break-all">{result.error}</p>}
          {result.success && (
            <div>
              <p className={`text-sm font-medium mb-2 ${theme === 'dark' ? 'text-slate-300' : 'text-slate-700'}`}>
                {result.tool_count} tool{result.tool_count !== 1 ? 's' : ''} discovered
              </p>
              <ToolsPanel tools={result.tools} />
            </div>
          )}
        </div>
        <div className={`px-6 py-4 border-t flex justify-end ${theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-gray-50 border-gray-200'}`}>
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700">Close</button>
        </div>
      </div>
    </div>
  )
}

// ── ToolCallBubble ────────────────────────────────────────────────────────────
function ToolCallBubble({ trace }: { trace: ToolCallTrace }) {
  const { theme } = useTheme()
  const [open, setOpen] = useState(false)
  const argsStr = typeof trace.args === 'object' ? JSON.stringify(trace.args, null, 2) : String(trace.args)
  return (
    <div className={`rounded-lg border text-xs overflow-hidden my-1 ${
      theme === 'dark' ? 'bg-slate-800/80 border-slate-700' : 'bg-gray-50 border-gray-200'
    }`}>
      <button onClick={() => setOpen(v => !v)}
        className={`w-full flex items-center gap-2 px-3 py-2 text-left hover:opacity-80 transition-opacity`}>
        <Wrench className="w-3 h-3 text-blue-400 flex-shrink-0" />
        <code className="font-mono text-blue-400 font-medium">{trace.tool_name}</code>
        <span className={`ml-auto ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>
          {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </span>
      </button>
      {open && (
        <div className={`border-t px-3 py-2 space-y-2 ${theme === 'dark' ? 'border-slate-700' : 'border-gray-200'}`}>
          <div>
            <p className={`text-xs font-medium mb-1 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Input</p>
            <pre className={`text-xs font-mono whitespace-pre-wrap break-all rounded p-2 ${
              theme === 'dark' ? 'bg-slate-900 text-slate-300' : 'bg-white text-slate-700 border border-gray-200'
            }`}>{argsStr}</pre>
          </div>
          <div>
            <p className={`text-xs font-medium mb-1 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Result</p>
            <pre className={`text-xs font-mono whitespace-pre-wrap break-all rounded p-2 max-h-40 overflow-y-auto ${
              theme === 'dark' ? 'bg-slate-900 text-emerald-300' : 'bg-white text-emerald-700 border border-gray-200'
            }`}>{trace.result}</pre>
          </div>
        </div>
      )}
    </div>
  )
}

// ── AgentChatPanel ────────────────────────────────────────────────────────────
function AgentChatPanel({ servers, preFill, onPreFillConsumed }: {
  servers: ServerWithStatus[]
  preFill?: string
  onPreFillConsumed?: () => void
}) {
  const { theme } = useTheme()
  const [messages, setMessages] = useState<MCPChatMessage[]>([])
  const [input, setInput] = useState('')

  useEffect(() => {
    if (preFill) { setInput(preFill); onPreFillConsumed?.() }
  }, [preFill]) // eslint-disable-line react-hooks/exhaustive-deps
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set())
  const [convId] = useState(() => `mcp-chat-${Date.now()}`)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const connectedServers = servers.filter(s => s.status.status === 'connected' && s.tools.length > 0)
  const allToolNames = connectedServers.flatMap(s => s.tools.map(t => `${t.server_name}/${t.name}`))

  const toggleTool = (name: string) => {
    setSelectedTools(prev => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }
  const toggleAll = () => {
    setSelectedTools(prev => prev.size === 0 ? new Set(allToolNames) : new Set())
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return
    const toolFilter = selectedTools.size > 0 ? [...selectedTools] : undefined
    const text = input.trim()
    setInput(''); setError(''); setLoading(true)
    setMessages(prev => [...prev, { role: 'user', content: text, tool_calls: [] }])
    try {
      const res = await mcpApi.chat(text, convId, toolFilter)
      setMessages(res.history)
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || 'Chat failed')
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${e?.response?.data?.detail || e.message}`, tool_calls: [] }])
    } finally { setLoading(false) }
  }

  const handleClear = async () => {
    await mcpApi.clearChatHistory(convId).catch(() => {})
    setMessages([])
  }

  const inputCls = `flex-1 px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50 ${
    theme === 'dark' ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500' : 'bg-white border-gray-300 text-slate-900 placeholder-gray-400'
  }`

  if (connectedServers.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center h-64 rounded-2xl border-2 border-dashed ${
        theme === 'dark' ? 'border-slate-700 text-slate-500' : 'border-gray-200 text-slate-400'
      }`}>
        <Bot className="w-10 h-10 mb-3 opacity-40" />
        <p className="font-medium">No connected MCP servers</p>
        <p className="text-sm mt-1">Connect a server from the Servers tab first</p>
      </div>
    )
  }

  return (
    <div className={`flex gap-4 h-[calc(100vh-200px)]`}>
      {/* Tool selector sidebar */}
      <div className={`w-64 flex-shrink-0 rounded-2xl border overflow-y-auto ${
        theme === 'dark' ? 'bg-slate-800/60 border-slate-700' : 'bg-white border-gray-200 shadow-sm'
      }`}>
        <div className={`px-4 py-3 border-b flex items-center justify-between ${theme === 'dark' ? 'border-slate-700' : 'border-gray-200'}`}>
          <span className={`text-sm font-semibold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Tools</span>
          <button onClick={toggleAll} className={`text-xs px-2 py-0.5 rounded-full border transition-all ${
            selectedTools.size === 0
              ? theme === 'dark' ? 'bg-blue-600/20 text-blue-400 border-blue-500/30' : 'bg-blue-50 text-blue-600 border-blue-200'
              : theme === 'dark' ? 'bg-slate-700 text-slate-400 border-slate-600 hover:bg-slate-600' : 'bg-gray-100 text-slate-600 border-gray-200 hover:bg-gray-200'
          }`}>
            {selectedTools.size === 0 ? 'All' : 'Custom'}
          </button>
        </div>
        <div className="p-3 space-y-3">
          {connectedServers.map(s => (
            <div key={s.config.id}>
              <p className={`text-xs font-semibold mb-1.5 flex items-center gap-1.5 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
                <Server className="w-3 h-3" />{s.config.name}
              </p>
              <div className="space-y-1">
                {s.tools.map(t => {
                  const fullName = `${t.server_name}/${t.name}`
                  const isActive = selectedTools.size === 0 || selectedTools.has(fullName)
                  return (
                    <label key={fullName} className="flex items-start gap-2 cursor-pointer group">
                      <input type="checkbox"
                        checked={selectedTools.size === 0 ? true : selectedTools.has(fullName)}
                        onChange={() => {
                          if (selectedTools.size === 0) {
                            const all = new Set(allToolNames)
                            all.delete(fullName)
                            setSelectedTools(all)
                          } else toggleTool(fullName)
                        }}
                        className="mt-0.5 w-3.5 h-3.5 rounded accent-blue-500 flex-shrink-0"
                      />
                      <div className="min-w-0">
                        <p className={`text-xs font-mono truncate ${
                          isActive
                            ? theme === 'dark' ? 'text-blue-300' : 'text-blue-600'
                            : theme === 'dark' ? 'text-slate-600' : 'text-slate-400'
                        }`}>{t.name}</p>
                        <p className={`text-xs truncate ${theme === 'dark' ? 'text-slate-600' : 'text-slate-400'}`}>{t.description.slice(0, 50)}</p>
                      </div>
                    </label>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Chat panel */}
      <div className={`flex-1 flex flex-col rounded-2xl border overflow-hidden ${
        theme === 'dark' ? 'bg-slate-800/60 border-slate-700' : 'bg-white border-gray-200 shadow-sm'
      }`}>
        {/* Chat header */}
        <div className={`px-4 py-3 border-b flex items-center justify-between ${theme === 'dark' ? 'border-slate-700' : 'border-gray-200'}`}>
          <div className="flex items-center gap-2">
            <Bot className={`w-4 h-4 ${theme === 'dark' ? 'text-emerald-400' : 'text-emerald-600'}`} />
            <span className={`text-sm font-semibold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>Agent Chat</span>
            <span className={`text-xs px-2 py-0.5 rounded-full border ${
              theme === 'dark' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-emerald-50 text-emerald-700 border-emerald-200'
            }`}>
              {selectedTools.size === 0 ? `${allToolNames.length} tools` : `${selectedTools.size} selected`}
            </span>
          </div>
          <button onClick={handleClear} title="Clear conversation"
            className={`p-1.5 rounded-lg transition-all ${theme === 'dark' ? 'hover:bg-slate-700 text-slate-400' : 'hover:bg-gray-100 text-slate-500'}`}>
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <Bot className={`w-10 h-10 mb-3 ${theme === 'dark' ? 'text-slate-600' : 'text-gray-300'}`} />
              <p className={`font-medium ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Ready to chat with your MCP tools</p>
              <p className={`text-sm mt-1 ${theme === 'dark' ? 'text-slate-600' : 'text-slate-400'}`}>
                The agent will automatically call the right tools based on your question.
              </p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[75%] space-y-1`}>
                  {msg.role === 'user' ? (
                    <div className={`px-4 py-2.5 rounded-2xl rounded-tr-sm text-sm ${
                      theme === 'dark' ? 'bg-blue-600 text-white' : 'bg-blue-500 text-white'
                    }`}>{msg.content}</div>
                  ) : (
                    <div>
                      {msg.tool_calls.length > 0 && (
                        <div className="mb-2 space-y-1">
                          {msg.tool_calls.map((tc, j) => <ToolCallBubble key={j} trace={tc} />)}
                        </div>
                      )}
                      <div className={`px-4 py-2.5 rounded-2xl rounded-tl-sm text-sm ${
                        theme === 'dark' ? 'bg-slate-700 text-slate-100' : 'bg-gray-100 text-slate-800'
                      }`}>{msg.content}</div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          {loading && (
            <div className="flex justify-start">
              <div className={`px-4 py-2.5 rounded-2xl rounded-tl-sm flex items-center gap-2 text-sm ${
                theme === 'dark' ? 'bg-slate-700 text-slate-400' : 'bg-gray-100 text-slate-500'
              }`}>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Agent thinking…</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className={`p-3 border-t ${theme === 'dark' ? 'border-slate-700' : 'border-gray-200'}`}>
          {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
          <div className="flex gap-2">
            <input
              className={inputCls}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              placeholder="Ask something — the agent will use MCP tools to answer…"
              disabled={loading}
            />
            <button onClick={handleSend} disabled={loading || !input.trim()}
              className="px-3 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-all flex-shrink-0">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function MCPServersPage() {
  const { theme } = useTheme()
  const [activeTab, setActiveTab] = useState<'servers' | 'chat'>('servers')
  const [servers, setServers] = useState<ServerWithStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [editTarget, setEditTarget] = useState<ServerWithStatus | null>(null)
  const [showImport, setShowImport] = useState(false)
  const [testResult, setTestResult] = useState<{ result: TestResult; name: string } | null>(null)
  const [testingId, setTestingId] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [chatPreFill, setChatPreFill] = useState('')

  const load = useCallback(async () => {
    try { setServers(await mcpApi.list()) } catch { /* ignore */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async (data: ServerCreateRequest) => {
    await mcpApi.create(data); await load()
  }
  const handleEdit = async (data: ServerCreateRequest, id?: string) => {
    if (!id) return; await mcpApi.patch(id, data); await load()
  }
  const handleConnect = async (id: string) => {
    await mcpApi.connect(id); await load()
  }
  const handleDisconnect = async (id: string) => {
    await mcpApi.disconnect(id); await load()
  }
  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return
    await mcpApi.delete(id); await load()
  }
  const handleTest = async (id: string, name: string) => {
    setTestingId(id)
    try { const result = await mcpApi.test(id); setTestResult({ result, name }) }
    finally { setTestingId(null) }
  }
  const [loginModal, setLoginModal] = useState<{ url: string; server: string } | null>(null)
  const [seedingNews, setSeedingNews] = useState(false)
  const handleSeedNews = async () => {
    setSeedingNews(true)
    try {
      await mcpApi.seedNews(true)
      await load()
    } catch (e: any) {
      alert(`Failed to add News Tools: ${e?.response?.data?.detail || e.message}`)
    } finally {
      setSeedingNews(false)
    }
  }
  const handleQuickLogin = async (serverId: string) => {
    try {
      const res = await mcpApi.login(serverId)
      // Extract URL from result string
      const urlMatch = res.result.match(/https?:\/\/[^\s"'<>]+/)
      if (urlMatch) {
        setLoginModal({ url: urlMatch[0], server: res.server })
      } else {
        setLoginModal({ url: '', server: res.server })
      }
      await load()
    } catch (e: any) {
      alert(`Login failed: ${e?.response?.data?.detail || e.message}`)
    }
  }

  const handleExport = async () => {
    const data = await mcpApi.export()
    const text = JSON.stringify(data, null, 2)
    await navigator.clipboard.writeText(text)
    setCopied(true); setTimeout(() => setCopied(false), 2000)
  }

  const connectedCount = servers.filter(s => s.status.status === 'connected').length
  const toolCount = servers.reduce((n, s) => n + s.status.tool_count, 0)

  return (
    <div className={`flex-1 overflow-y-auto p-6 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
      {/* Page header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
        <div>
          <h1 className={`text-2xl font-bold ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>MCP Servers</h1>
          <p className={`text-sm mt-0.5 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
            {servers.length} configured · {connectedCount} connected · {toolCount} tool{toolCount !== 1 ? 's' : ''} available
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button onClick={load} className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border transition-all ${
            theme === 'dark' ? 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700' : 'bg-white text-slate-600 border-gray-200 hover:bg-gray-50'
          }`}><RefreshCw className="w-4 h-4" /> Refresh</button>
          <button onClick={() => setShowImport(true)} className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border transition-all ${
            theme === 'dark' ? 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700' : 'bg-white text-slate-600 border-gray-200 hover:bg-gray-50'
          }`}><Upload className="w-4 h-4" /> Import</button>
          <button onClick={handleExport} className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border transition-all ${
            theme === 'dark' ? 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700' : 'bg-white text-slate-600 border-gray-200 hover:bg-gray-50'
          }`}>
            {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            {copied ? 'Copied!' : 'Export'}
          </button>
          {!servers.some(s => s.config.name === 'RAGenie News') && (
            <button onClick={handleSeedNews} disabled={seedingNews}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-all disabled:opacity-50">
              {seedingNews ? <Loader2 className="w-4 h-4 animate-spin" /> : <Newspaper className="w-4 h-4" />}
              News Tools
            </button>
          )}
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-all">
            <Plus className="w-4 h-4" /> Add Server
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div className={`flex gap-1 mb-6 p-1 rounded-xl w-fit border ${theme === 'dark' ? 'bg-slate-800/60 border-slate-700' : 'bg-gray-100 border-gray-200'}`}>
        {(['servers', 'chat'] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab
                ? theme === 'dark' ? 'bg-slate-700 text-white shadow-sm' : 'bg-white text-slate-900 shadow-sm'
                : theme === 'dark' ? 'text-slate-400 hover:text-white' : 'text-slate-500 hover:text-slate-900'
            }`}>
            {tab === 'servers' ? <Server className="w-4 h-4" /> : <MessageSquare className="w-4 h-4" />}
            {tab === 'servers' ? 'Servers' : 'Agent Chat'}
          </button>
        ))}
      </div>

      {activeTab === 'chat' ? (
        <AgentChatPanel
          servers={servers}
          preFill={chatPreFill}
          onPreFillConsumed={() => setChatPreFill('')}
        />
      ) : loading ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : servers.length === 0 ? (
        <div className={`flex flex-col items-center justify-center h-64 rounded-2xl border-2 border-dashed ${
          theme === 'dark' ? 'border-slate-700 text-slate-500' : 'border-gray-200 text-slate-400'
        }`}>
          <Wrench className="w-10 h-10 mb-3 opacity-40" />
          <p className="font-medium">No MCP servers configured</p>
          <p className="text-sm mt-1">Add a server to connect RAGenie to external tools</p>
          <button onClick={() => setShowAdd(true)}
            className="mt-4 flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-all">
            <Plus className="w-4 h-4" /> Add your first server
          </button>
        </div>
      ) : (
        <div className="grid gap-4 grid-cols-1 lg:grid-cols-2 xl:grid-cols-3">
          {servers.map(item => (
            <ServerCard
              key={item.config.id}
              item={item}
              onConnect={() => handleConnect(item.config.id)}
              onDisconnect={() => handleDisconnect(item.config.id)}
              onDelete={() => handleDelete(item.config.id, item.config.name)}
              onTest={() => handleTest(item.config.id, item.config.name)}
              onEdit={() => setEditTarget(item)}
              onQuickLogin={handleQuickLogin}
            />

          ))}
        </div>
      )}

      {/* Hint box */}
      {activeTab === 'servers' && servers.length > 0 && connectedCount > 0 && (
        <div className={`mt-6 p-4 rounded-xl border text-sm ${
          theme === 'dark' ? 'bg-blue-900/20 border-blue-500/20 text-blue-300' : 'bg-blue-50 border-blue-200 text-blue-700'
        }`}>
          <strong>{toolCount} tool{toolCount !== 1 ? 's' : ''}</strong> are now available. Use the
          <button onClick={() => setActiveTab('chat')} className="mx-1 underline underline-offset-2 font-semibold">
            Agent Chat tab
          </button>
          or enable <code className="font-mono text-xs px-1 py-0.5 rounded bg-blue-500/10">Agent Mode</code> in the main Chat.
        </div>
      )}

      {/* Login URL modal */}
      {loginModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className={`rounded-2xl shadow-2xl w-full max-w-lg p-6 ${theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'}`}>
            <h2 className={`text-lg font-semibold mb-1 ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
              Login to {loginModal.server}
            </h2>
            <p className={`text-sm mb-4 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
              Open the link below in your browser to authenticate, then return here.
            </p>
            {loginModal.url ? (
              <>
                <div className={`rounded-lg p-3 text-xs font-mono break-all mb-4 ${theme === 'dark' ? 'bg-slate-900 text-emerald-300' : 'bg-gray-50 text-emerald-700 border border-gray-200'}`}>
                  {loginModal.url}
                </div>
                <div className="flex gap-2 flex-wrap">
                  <a href={loginModal.url} target="_blank" rel="noopener noreferrer"
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-emerald-500 text-white hover:bg-emerald-600 transition-all">
                    <LogIn className="w-4 h-4" /> Open in Browser
                  </a>
                  <button onClick={() => { navigator.clipboard.writeText(loginModal.url); }}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium border transition-all ${theme === 'dark' ? 'bg-slate-700 text-slate-300 border-slate-600 hover:bg-slate-600' : 'bg-gray-100 text-slate-600 border-gray-200 hover:bg-gray-200'}`}>
                    Copy Link
                  </button>
                  <button onClick={() => setLoginModal(null)}
                    className={`ml-auto px-4 py-2 rounded-lg text-sm border transition-all ${theme === 'dark' ? 'text-slate-400 border-slate-600 hover:bg-slate-700' : 'text-slate-500 border-gray-200 hover:bg-gray-50'}`}>
                    Close
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className={`rounded-lg p-3 text-sm mb-4 ${theme === 'dark' ? 'bg-slate-900 text-slate-300' : 'bg-gray-50 text-slate-700 border border-gray-200'}`}>
                  No URL found in response. The server may have returned a different kind of response.
                </div>
                <button onClick={() => setLoginModal(null)}
                  className={`px-4 py-2 rounded-lg text-sm border transition-all ${theme === 'dark' ? 'text-slate-400 border-slate-600 hover:bg-slate-700' : 'text-slate-500 border-gray-200 hover:bg-gray-50'}`}>
                  Close
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Modals */}
      {showAdd && <ServerFormModal onSave={handleCreate} onClose={() => setShowAdd(false)} />}
      {editTarget && (
        <ServerFormModal
          initial={{ ...editTarget.config, id: editTarget.config.id, connect_now: false }}
          onSave={handleEdit}
          onClose={() => setEditTarget(null)}
        />
      )}
      {showImport && <ImportModal onClose={() => setShowImport(false)} onDone={load} />}
      {testResult && (
        <TestResultModal
          result={testResult.result}
          name={testResult.name}
          onClose={() => setTestResult(null)}
        />
      )}

      {/* Per-card test loading overlay */}
      {testingId && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 flex items-center justify-center">
          <div className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl ${theme === 'dark' ? 'bg-slate-800' : 'bg-white'}`}>
            <Loader2 className="w-5 h-5 animate-spin text-blue-400" />
            <span className={theme === 'dark' ? 'text-slate-200' : 'text-slate-700'}>Testing connection…</span>
          </div>
        </div>
      )}
    </div>
  )
}
