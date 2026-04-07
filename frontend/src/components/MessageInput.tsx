import { useState, useEffect, KeyboardEvent } from 'react'
import { Send, Trash2, Loader2, Brain, History } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'

interface MessageInputProps {
  onSendMessage: (message: string, useReasoning?: boolean) => void
  onClearHistory: () => void
  isLoading: boolean
  disabled: boolean
  processingStatus?: string
  isHistoryOpen?: boolean
  onToggleHistory?: () => void
  hasHistory?: boolean
  pendingQuery?: string | null
  onPendingQueryConsumed?: () => void
}

export default function MessageInput({ 
  onSendMessage, 
  onClearHistory, 
  isLoading, 
  disabled,
  processingStatus = '',
  isHistoryOpen = false,
  onToggleHistory,
  hasHistory = false,
  pendingQuery = null,
  onPendingQueryConsumed
}: MessageInputProps) {
  const [input, setInput] = useState('')
  const [useReasoning, setUseReasoning] = useState(false)
  const [autoDetectReasoning, setAutoDetectReasoning] = useState(true)
  const { theme } = useTheme()

  // Fill input when a history item is selected from the panel
  useEffect(() => {
    if (pendingQuery) {
      setInput(pendingQuery)
      onPendingQueryConsumed?.()
    }
  }, [pendingQuery, onPendingQueryConsumed])

  const handleSubmit = () => {
    if (input.trim() && !disabled) {
      // Auto-detect if reasoning is needed
      let shouldUseReasoning = useReasoning
      if (autoDetectReasoning) {
        const reasoningKeywords = [
          'step by step', 'explain', 'how to', 'why does', 'solve', 'calculate',
          'analyze', 'compare', 'derive', 'prove', 'show work', 'break down',
          'step-by-step', 'process', 'method', 'derive', 'demonstrate'
        ]
        const lowerInput = input.toLowerCase()
        shouldUseReasoning = reasoningKeywords.some(keyword => lowerInput.includes(keyword))
      }
      
      onSendMessage(input.trim(), shouldUseReasoning)
      setInput('')
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className={`border-t backdrop-blur-2xl p-4 transition-colors ${
      theme === 'dark'
        ? 'border-slate-700/50 bg-slate-900/80'
        : 'border-gray-200 bg-white/80'
    }`}>
      <div className="max-w-4xl mx-auto flex gap-3">
        <div className="flex gap-2">
          <button
            onClick={onClearHistory}
            disabled={disabled}
            className={`p-3 rounded-xl backdrop-blur-xl border disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg ${
              theme === 'dark'
                ? 'bg-slate-800 border-slate-700 hover:bg-slate-700 text-white'
                : 'bg-gray-100 border-gray-200 hover:bg-gray-200 text-slate-700'
            }`}
            title="Clear chat"
          >
            <Trash2 className="w-5 h-5" />
          </button>
          
          {onToggleHistory && hasHistory && (
            <button
              onClick={onToggleHistory}
              className={`p-3 rounded-xl backdrop-blur-xl border transition-all shadow-lg ${
                isHistoryOpen
                  ? theme === 'dark'
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-blue-500 border-blue-400 text-white'
                  : theme === 'dark'
                    ? 'bg-slate-800 border-slate-700 hover:bg-slate-700 text-white'
                    : 'bg-gray-100 border-gray-200 hover:bg-gray-200 text-slate-700'
              }`}
              title={isHistoryOpen ? 'Hide search history' : 'Show search history'}
            >
              <History className="w-5 h-5" />
            </button>
          )}
          
          <button
            onClick={() => setAutoDetectReasoning(!autoDetectReasoning)}
            disabled={disabled}
            className={`px-3 py-3 rounded-xl backdrop-blur-xl border disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg text-sm font-medium ${
              autoDetectReasoning
                ? theme === 'dark'
                  ? 'bg-purple-600 border-purple-500 text-white'
                  : 'bg-purple-500 border-purple-400 text-white'
                : theme === 'dark'
                  ? 'bg-slate-800 border-slate-700 hover:bg-slate-700 text-white'
                  : 'bg-gray-100 border-gray-200 hover:bg-gray-200 text-slate-700'
            }`}
            title="Auto-detect reasoning mode"
          >
            Auto
          </button>
          
          {!autoDetectReasoning && (
            <button
              onClick={() => setUseReasoning(!useReasoning)}
              disabled={disabled}
              className={`p-3 rounded-xl backdrop-blur-xl border disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg ${
                useReasoning
                  ? theme === 'dark'
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-blue-500 border-blue-400 text-white'
                  : theme === 'dark'
                    ? 'bg-slate-800 border-slate-700 hover:bg-slate-700 text-white'
                    : 'bg-gray-100 border-gray-200 hover:bg-gray-200 text-slate-700'
              }`}
              title="Toggle reasoning mode"
            >
              <Brain className="w-5 h-5" />
            </button>
          )}
        </div>

        <div className="flex-1 relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={processingStatus || "Type your message... (Shift+Enter for new line)"}
            disabled={disabled || isLoading}
            rows={1}
            className={`w-full px-4 py-3 backdrop-blur-xl border rounded-xl resize-none focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg ${
              theme === 'dark'
                ? 'bg-slate-800 border-slate-700 text-white placeholder-slate-500 focus:ring-blue-500 focus:border-blue-500'
                : 'bg-white border-gray-200 text-slate-900 placeholder-slate-400 focus:ring-blue-500 focus:border-blue-400'
            }`}
            style={{ minHeight: '48px', maxHeight: '200px' }}
          />
          {processingStatus && (
            <div className={`absolute top-2 right-2 text-xs px-2 py-1 rounded-full ${
              theme === 'dark' ? 'bg-blue-600 text-white' : 'bg-blue-100 text-blue-700'
            }`}>
              {processingStatus}
            </div>
          )}
        </div>

        <button
          onClick={handleSubmit}
          disabled={disabled || !input.trim()}
          className={`p-3 rounded-xl backdrop-blur-xl border disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg ${
            theme === 'dark'
              ? 'bg-blue-600 border-blue-500 hover:bg-blue-500 text-white'
              : 'bg-blue-500 border-blue-400 hover:bg-blue-600 text-white'
          }`}
          title="Send message"
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </button>
      </div>
    </div>
  )
}
