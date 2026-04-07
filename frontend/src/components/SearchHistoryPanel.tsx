import { useState } from 'react'
import { History, Clock, X, Trash2, Search } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import { SearchHistoryItem } from '../hooks/useSearchHistory'

interface SearchHistoryPanelProps {
  history: SearchHistoryItem[]
  onSelect: (query: string) => void
  onRemove: (query: string) => void
  onClear: () => void
  onClose: () => void
}

export default function SearchHistoryPanel({
  history,
  onSelect,
  onRemove,
  onClear,
  onClose,
}: SearchHistoryPanelProps) {
  const { theme } = useTheme()
  const [filter, setFilter] = useState('')

  const filtered = filter.trim()
    ? history.filter(item =>
        item.query.toLowerCase().includes(filter.toLowerCase())
      )
    : history

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  return (
    <div className={`w-80 flex flex-col border-l transition-colors ${
      theme === 'dark'
        ? 'bg-slate-900/95 border-slate-700/50'
        : 'bg-white/95 border-gray-200'
    }`}>
      {/* Header */}
      <div className={`flex items-center justify-between px-4 py-3 border-b ${
        theme === 'dark' ? 'border-slate-700/50' : 'border-gray-200'
      }`}>
        <div className="flex items-center gap-2">
          <History className={`w-4 h-4 ${
            theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
          }`} />
          <h3 className={`text-sm font-semibold ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>
            Search History
          </h3>
          <span className={`text-xs px-1.5 py-0.5 rounded-full ${
            theme === 'dark' ? 'bg-slate-700 text-slate-400' : 'bg-gray-100 text-slate-500'
          }`}>
            {history.length}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {history.length > 0 && (
            <button
              onClick={onClear}
              className={`p-1.5 rounded-lg transition-colors ${
                theme === 'dark'
                  ? 'hover:bg-slate-700 text-slate-400 hover:text-red-400'
                  : 'hover:bg-gray-100 text-slate-400 hover:text-red-500'
              }`}
              title="Clear all history"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={onClose}
            className={`p-1.5 rounded-lg transition-colors ${
              theme === 'dark'
                ? 'hover:bg-slate-700 text-slate-400'
                : 'hover:bg-gray-100 text-slate-500'
            }`}
            title="Close panel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filter Input */}
      <div className={`px-3 py-2 border-b ${
        theme === 'dark' ? 'border-slate-700/50' : 'border-gray-100'
      }`}>
        <div className="relative">
          <Search className={`absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 ${
            theme === 'dark' ? 'text-slate-500' : 'text-slate-400'
          }`} />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter history..."
            className={`w-full pl-8 pr-3 py-1.5 text-sm rounded-lg border focus:outline-none focus:ring-1 transition-colors ${
              theme === 'dark'
                ? 'bg-slate-800 border-slate-700 text-white placeholder-slate-500 focus:ring-blue-500'
                : 'bg-gray-50 border-gray-200 text-slate-900 placeholder-slate-400 focus:ring-blue-500'
            }`}
          />
        </div>
      </div>

      {/* History List */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className={`flex flex-col items-center justify-center h-full px-4 ${
            theme === 'dark' ? 'text-slate-500' : 'text-slate-400'
          }`}>
            <History className="w-8 h-8 mb-2 opacity-50" />
            <p className="text-sm text-center">
              {history.length === 0
                ? 'No search history yet.\nYour queries will appear here.'
                : 'No matches found.'}
            </p>
          </div>
        ) : (
          filtered.map((item) => (
            <div
              key={item.query + item.timestamp}
              className={`group flex items-start gap-2.5 px-4 py-2.5 cursor-pointer border-b transition-colors ${
                theme === 'dark'
                  ? 'border-slate-800 hover:bg-slate-800/80'
                  : 'border-gray-50 hover:bg-blue-50/50'
              }`}
              onClick={() => onSelect(item.query)}
            >
              <Clock className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${
                theme === 'dark' ? 'text-slate-600' : 'text-slate-300'
              }`} />
              <div className="flex-1 min-w-0">
                <p className={`text-sm leading-snug break-words ${
                  theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                }`}>
                  {item.query}
                </p>
                <p className={`text-xs mt-0.5 ${
                  theme === 'dark' ? 'text-slate-600' : 'text-slate-400'
                }`}>
                  {formatTime(item.timestamp)}
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onRemove(item.query)
                }}
                className={`opacity-0 group-hover:opacity-100 p-1 rounded transition-all flex-shrink-0 ${
                  theme === 'dark'
                    ? 'hover:bg-slate-700 text-slate-500 hover:text-red-400'
                    : 'hover:bg-gray-200 text-slate-400 hover:text-red-500'
                }`}
                title="Remove"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
