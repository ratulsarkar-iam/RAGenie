import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Activity as ActivityIcon, LogIn, LogOut, MessageSquare, FileUp, FileX,
  Tag, TagsIcon, Trash2, Newspaper, Zap, Plug, PlugZap, Unplug, Wrench,
  Brain, Search, ChevronDown, Loader2, Users, RotateCcw,
} from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'
import { activityApi, ActivityEvent, ACTIVITY_EVENT_TYPES } from '../api/activityApi'
import { authApi, AuthUser } from '../api/authApi'

const EVENT_ICONS: Record<string, JSX.Element> = {
  login: <LogIn className="w-4 h-4 text-emerald-400" />,
  logout: <LogOut className="w-4 h-4 text-slate-400" />,
  chat_message: <MessageSquare className="w-4 h-4 text-blue-400" />,
  document_uploaded: <FileUp className="w-4 h-4 text-purple-400" />,
  document_deleted: <FileX className="w-4 h-4 text-red-400" />,
  keyword_created: <Tag className="w-4 h-4 text-cyan-400" />,
  keyword_updated: <TagsIcon className="w-4 h-4 text-cyan-400" />,
  keyword_deleted: <Trash2 className="w-4 h-4 text-red-400" />,
  news_search: <Newspaper className="w-4 h-4 text-amber-400" />,
  news_fetch_now: <Zap className="w-4 h-4 text-amber-400" />,
  mcp_server_created: <Plug className="w-4 h-4 text-indigo-400" />,
  mcp_server_updated: <Plug className="w-4 h-4 text-indigo-400" />,
  mcp_server_deleted: <Unplug className="w-4 h-4 text-red-400" />,
  mcp_server_connected: <PlugZap className="w-4 h-4 text-emerald-400" />,
  mcp_server_disconnected: <Unplug className="w-4 h-4 text-slate-400" />,
  mcp_tool_call: <Wrench className="w-4 h-4 text-indigo-400" />,
  memory_search: <Brain className="w-4 h-4 text-purple-400" />,
}

function eventIcon(eventType: string): JSX.Element {
  return EVENT_ICONS[eventType] || <ActivityIcon className="w-4 h-4 text-slate-400" />
}

function formatRelativeTime(iso: string): string {
  const date = new Date(iso)
  const diffMs = Date.now() - date.getTime()
  const diffSec = Math.round(diffMs / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.round(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.round(diffHr / 24)
  if (diffDay < 30) return `${diffDay}d ago`
  return date.toLocaleDateString()
}

function dayLabel(iso: string): string {
  const date = new Date(iso)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  if (date.toDateString() === today.toDateString()) return 'Today'
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
}

const PAGE_LIMIT = 30

export default function ActivityPage() {
  const { theme } = useTheme()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [events, setEvents] = useState<ActivityEvent[]>([])
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('')
  const [search, setSearch] = useState('')
  const [selectedUserId, setSelectedUserId] = useState<string>('') // '' = my activity
  const [users, setUsers] = useState<AuthUser[]>([])

  useEffect(() => {
    if (isAdmin) {
      authApi.listUsers().then(setUsers).catch(() => {})
    }
  }, [isAdmin])

  const fetchPage = useCallback(async (targetPage: number, replace: boolean) => {
    setLoading(true)
    setError(null)
    try {
      const params = { event_type: eventTypeFilter || undefined, page: targetPage, limit: PAGE_LIMIT }
      const data = selectedUserId
        ? await activityApi.listAll({ ...params, user_id: selectedUserId })
        : await activityApi.listMine(params)
      setEvents(prev => (replace ? data : [...prev, ...data]))
      setHasMore(data.length === PAGE_LIMIT)
      setPage(targetPage)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load activity')
    } finally {
      setLoading(false)
    }
  }, [eventTypeFilter, selectedUserId])

  useEffect(() => {
    fetchPage(1, true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventTypeFilter, selectedUserId])

  const filteredEvents = useMemo(() => {
    if (!search.trim()) return events
    const q = search.toLowerCase()
    return events.filter(e => e.description.toLowerCase().includes(q))
  }, [events, search])

  const grouped = useMemo(() => {
    const groups: { label: string; items: ActivityEvent[] }[] = []
    for (const evt of filteredEvents) {
      const label = dayLabel(evt.created_at)
      const last = groups[groups.length - 1]
      if (last && last.label === label) {
        last.items.push(evt)
      } else {
        groups.push({ label, items: [evt] })
      }
    }
    return groups
  }, [filteredEvents])

  const cardBg = theme === 'dark' ? 'bg-slate-800/50 border-slate-700' : 'bg-gray-50 border-gray-200'
  const textMuted = theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
  const textMain = theme === 'dark' ? 'text-white' : 'text-slate-900'

  return (
    <div className="flex-1 min-w-0 overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <ActivityIcon className={`w-6 h-6 ${theme === 'dark' ? 'text-blue-400' : 'text-blue-500'}`} />
          <h1 className={`text-xl font-semibold ${textMain}`}>Activity Log</h1>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          {isAdmin && (
            <div className="relative">
              <Users className={`w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 ${textMuted}`} />
              <select
                value={selectedUserId}
                onChange={e => setSelectedUserId(e.target.value)}
                className={`pl-9 pr-8 py-2 rounded-xl border text-sm appearance-none cursor-pointer ${
                  theme === 'dark' ? 'bg-slate-800 border-slate-700 text-slate-200' : 'bg-white border-gray-200 text-slate-700'
                }`}
              >
                <option value="">My Activity</option>
                {users.map(u => (
                  <option key={u.id} value={u.id}>{u.email}</option>
                ))}
              </select>
              <ChevronDown className={`w-4 h-4 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none ${textMuted}`} />
            </div>
          )}

          <div className="relative">
            <select
              value={eventTypeFilter}
              onChange={e => setEventTypeFilter(e.target.value)}
              className={`pl-3 pr-8 py-2 rounded-xl border text-sm appearance-none cursor-pointer ${
                theme === 'dark' ? 'bg-slate-800 border-slate-700 text-slate-200' : 'bg-white border-gray-200 text-slate-700'
              }`}
            >
              <option value="">All event types</option>
              {ACTIVITY_EVENT_TYPES.map(t => (
                <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
              ))}
            </select>
            <ChevronDown className={`w-4 h-4 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none ${textMuted}`} />
          </div>

          <div className={`flex items-center gap-2 rounded-xl border px-3 py-2 flex-1 min-w-[180px] ${
            theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'
          }`}>
            <Search className={`w-4 h-4 flex-shrink-0 ${textMuted}`} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search description…"
              className={`flex-1 bg-transparent outline-none text-sm ${textMain} placeholder-slate-500`}
            />
          </div>

          <button
            onClick={() => fetchPage(1, true)}
            className={`p-2 rounded-xl border transition-all ${
              theme === 'dark' ? 'bg-slate-800 border-slate-700 hover:bg-slate-700 text-slate-300' : 'bg-white border-gray-200 hover:bg-gray-100 text-slate-600'
            }`}
            title="Refresh"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="text-sm text-red-400 mb-4">{error} — <button className="underline" onClick={() => fetchPage(1, true)}>retry</button></div>
        )}

        {/* Empty state */}
        {!loading && grouped.length === 0 && !error && (
          <div className={`text-center py-16 ${textMuted}`}>
            <ActivityIcon className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p>No activity yet.</p>
          </div>
        )}

        {/* Feed */}
        <div className="space-y-6">
          {grouped.map(group => (
            <div key={group.label}>
              <div className={`text-xs font-semibold uppercase tracking-wide mb-2 ${textMuted}`}>{group.label}</div>
              <div className="space-y-2">
                {group.items.map(evt => (
                  <ActivityRow key={evt.id} event={evt} cardBg={cardBg} textMain={textMain} textMuted={textMuted} theme={theme} />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Load more */}
        {hasMore && grouped.length > 0 && (
          <div className="flex justify-center mt-6">
            <button
              onClick={() => fetchPage(page + 1, false)}
              disabled={loading}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all disabled:opacity-60 ${
                theme === 'dark' ? 'bg-slate-800 hover:bg-slate-700 text-slate-300' : 'bg-gray-100 hover:bg-gray-200 text-slate-700'
              }`}
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin inline" /> : 'Load more'}
            </button>
          </div>
        )}

        {loading && grouped.length === 0 && (
          <div className="flex justify-center py-12">
            <Loader2 className={`w-6 h-6 animate-spin ${theme === 'dark' ? 'text-blue-400' : 'text-blue-500'}`} />
          </div>
        )}
      </div>
    </div>
  )
}

function ActivityRow({
  event, cardBg, textMain, textMuted, theme,
}: { event: ActivityEvent; cardBg: string; textMain: string; textMuted: string; theme: string }) {
  const [expanded, setExpanded] = useState(false)
  const hasMetadata = event.metadata && Object.keys(event.metadata).length > 0

  return (
    <div className={`backdrop-blur-xl border rounded-xl p-3 transition-all ${cardBg}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex-shrink-0">{eventIcon(event.event_type)}</div>
        <div className="flex-1 min-w-0">
          <p className={`text-sm ${textMain}`}>{event.description}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-xs ${textMuted}`}>{formatRelativeTime(event.created_at)}</span>
            {hasMetadata && (
              <button
                onClick={() => setExpanded(!expanded)}
                className={`text-xs underline ${textMuted}`}
              >
                {expanded ? 'hide details' : 'details'}
              </button>
            )}
          </div>
          {expanded && hasMetadata && (
            <pre className={`mt-2 text-xs p-2 rounded-lg overflow-x-auto ${
              theme === 'dark' ? 'bg-slate-900 text-slate-300' : 'bg-white text-slate-700'
            }`}>
              {JSON.stringify(event.metadata, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}
