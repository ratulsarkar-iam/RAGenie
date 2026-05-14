import { useState, useEffect, useRef, KeyboardEvent, DragEvent, ChangeEvent } from 'react'
import { Send, Trash2, Loader2, Brain, History, Paperclip, X, FileText, Image, Music, FileSpreadsheet, Bot } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'

const MAX_FILE_SIZE = 30 * 1024 * 1024 // 30MB
const ALLOWED_EXTENSIONS = [
  '.txt', '.pdf', '.md', '.markdown',
  '.docx', '.doc',
  '.xlsx', '.xls', '.csv',
  '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg',
  '.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma',
]
const ACCEPT_STRING = ALLOWED_EXTENSIONS.join(',')

function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'svg'].includes(ext)) return Image
  if (['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma'].includes(ext)) return Music
  if (['xlsx', 'xls', 'csv'].includes(ext)) return FileSpreadsheet
  return FileText
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

interface MessageInputProps {
  onSendMessage: (message: string, useReasoning?: boolean, files?: File[], useAgent?: boolean) => void
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
  const [useAgent, setUseAgent] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState<File[]>([])
  const [isDragOver, setIsDragOver] = useState(false)
  const [fileError, setFileError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { theme } = useTheme()

  // Fill input when a history item is selected from the panel
  useEffect(() => {
    if (pendingQuery) {
      setInput(pendingQuery)
      onPendingQueryConsumed?.()
    }
  }, [pendingQuery, onPendingQueryConsumed])

  const handleSubmit = () => {
    if ((!input.trim() && attachedFiles.length === 0) || disabled) return

    // Auto-detect if reasoning is needed
    let shouldUseReasoning = useReasoning
    if (autoDetectReasoning && input.trim()) {
      const reasoningKeywords = [
        'step by step', 'explain', 'how to', 'why does', 'solve', 'calculate',
        'analyze', 'compare', 'derive', 'prove', 'show work', 'break down',
        'step-by-step', 'process', 'method', 'derive', 'demonstrate'
      ]
      const lowerInput = input.toLowerCase()
      shouldUseReasoning = reasoningKeywords.some(keyword => lowerInput.includes(keyword))
    }
    
    onSendMessage(input.trim(), shouldUseReasoning, attachedFiles.length > 0 ? attachedFiles : undefined, useAgent)
    setInput('')
    setAttachedFiles([])
    setFileError('')
  }

  const validateAndAddFiles = (files: FileList | File[]) => {
    setFileError('')
    const newFiles: File[] = []
    for (const file of Array.from(files)) {
      const ext = '.' + file.name.split('.').pop()?.toLowerCase()
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        setFileError(`Unsupported file type: ${ext}`)
        continue
      }
      if (file.size > MAX_FILE_SIZE) {
        setFileError(`File too large: ${file.name} (${formatSize(file.size)}). Max 30MB.`)
        continue
      }
      // Prevent duplicates
      if (!attachedFiles.some(f => f.name === file.name && f.size === file.size)) {
        newFiles.push(file)
      }
    }
    if (newFiles.length > 0) {
      setAttachedFiles(prev => [...prev, ...newFiles])
    }
  }

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndAddFiles(e.target.files)
    }
    // Reset so same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(true)
  }

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
  }

  const handleDrop = (e: DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndAddFiles(e.dataTransfer.files)
    }
  }

  const removeFile = (index: number) => {
    setAttachedFiles(prev => prev.filter((_, i) => i !== index))
    setFileError('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className={`border-t backdrop-blur-2xl px-4 py-3 transition-colors ${
      theme === 'dark'
        ? 'border-slate-700/50 bg-slate-900/80'
        : 'border-gray-200 bg-white/80'
    }`}>
      <div
        className={`max-w-4xl mx-auto rounded-2xl border transition-all overflow-hidden ${
          isDragOver
            ? theme === 'dark'
              ? 'border-blue-500 bg-blue-900/20 ring-2 ring-blue-500/40'
              : 'border-blue-500 bg-blue-50 ring-2 ring-blue-500/30'
            : theme === 'dark'
              ? 'border-slate-700 bg-slate-800/80'
              : 'border-gray-200 bg-white'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Attached files preview */}
        {attachedFiles.length > 0 && (
          <div className={`flex flex-wrap gap-2 px-3 pt-3 pb-1 ${
            theme === 'dark' ? 'border-slate-700/50' : 'border-gray-100'
          }`}>
            {attachedFiles.map((file, idx) => {
              const IconComp = getFileIcon(file.name)
              return (
                <div
                  key={file.name + file.size}
                  className={`flex items-center gap-1.5 pl-2.5 pr-1.5 py-1.5 rounded-lg text-xs font-medium border ${
                    theme === 'dark'
                      ? 'bg-slate-700/70 border-slate-600 text-slate-300'
                      : 'bg-gray-50 border-gray-200 text-slate-600'
                  }`}
                >
                  <IconComp className={`w-3.5 h-3.5 flex-shrink-0 ${
                    theme === 'dark' ? 'text-blue-400' : 'text-blue-500'
                  }`} />
                  <span className="truncate max-w-[140px]">{file.name}</span>
                  <span className={theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}>
                    {formatSize(file.size)}
                  </span>
                  <button
                    onClick={() => removeFile(idx)}
                    className={`ml-0.5 p-0.5 rounded-md transition-colors ${
                      theme === 'dark'
                        ? 'text-slate-500 hover:text-red-400 hover:bg-red-500/10'
                        : 'text-slate-400 hover:text-red-500 hover:bg-red-50'
                    }`}
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {fileError && (
          <div className="px-3 pt-2 text-xs text-red-500 font-medium">{fileError}</div>
        )}

        {/* Textarea */}
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isDragOver
              ? 'Drop files here...'
              : processingStatus || 'Type your message... (Shift+Enter for new line)'
          }
          disabled={disabled || isLoading}
          rows={1}
          className={`w-full px-4 pt-3 pb-2 bg-transparent resize-none focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed ${
            theme === 'dark'
              ? 'text-white placeholder-slate-500'
              : 'text-slate-900 placeholder-slate-400'
          }`}
          style={{ minHeight: '44px', maxHeight: '160px' }}
        />

        {/* Bottom toolbar */}
        <div className={`flex items-center justify-between px-3 pb-2.5 pt-0.5`}>
          {/* Left actions */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled || isLoading}
              className={`p-2 rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${
                theme === 'dark'
                  ? 'text-slate-400 hover:text-white hover:bg-slate-700'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-gray-100'
              }`}
              title="Attach file (max 30MB)"
            >
              <Paperclip className="w-[18px] h-[18px]" />
            </button>

            <div className={`w-px h-5 mx-1 ${
              theme === 'dark' ? 'bg-slate-700' : 'bg-gray-200'
            }`} />

            <button
              onClick={onClearHistory}
              disabled={disabled}
              className={`p-2 rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${
                theme === 'dark'
                  ? 'text-slate-400 hover:text-white hover:bg-slate-700'
                  : 'text-slate-500 hover:text-slate-700 hover:bg-gray-100'
              }`}
              title="Clear chat"
            >
              <Trash2 className="w-[18px] h-[18px]" />
            </button>

            {onToggleHistory && hasHistory && (
              <button
                onClick={onToggleHistory}
                className={`p-2 rounded-lg transition-colors ${
                  isHistoryOpen
                    ? theme === 'dark'
                      ? 'text-blue-400 bg-blue-500/15'
                      : 'text-blue-600 bg-blue-50'
                    : theme === 'dark'
                      ? 'text-slate-400 hover:text-white hover:bg-slate-700'
                      : 'text-slate-500 hover:text-slate-700 hover:bg-gray-100'
                }`}
                title={isHistoryOpen ? 'Hide search history' : 'Show search history'}
              >
                <History className="w-[18px] h-[18px]" />
              </button>
            )}

            <div className={`w-px h-5 mx-1 ${
              theme === 'dark' ? 'bg-slate-700' : 'bg-gray-200'
            }`} />

            <button
              onClick={() => setAutoDetectReasoning(!autoDetectReasoning)}
              disabled={disabled}
              className={`px-2 py-1 rounded-lg text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${
                autoDetectReasoning
                  ? theme === 'dark'
                    ? 'text-purple-300 bg-purple-500/15'
                    : 'text-purple-600 bg-purple-50'
                  : theme === 'dark'
                    ? 'text-slate-400 hover:text-white hover:bg-slate-700'
                    : 'text-slate-500 hover:text-slate-700 hover:bg-gray-100'
              }`}
              title="Auto-detect reasoning mode"
            >
              Auto
            </button>

            {!autoDetectReasoning && (
              <button
                onClick={() => setUseReasoning(!useReasoning)}
                disabled={disabled}
                className={`p-2 rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${
                  useReasoning
                    ? theme === 'dark'
                      ? 'text-blue-400 bg-blue-500/15'
                      : 'text-blue-600 bg-blue-50'
                    : theme === 'dark'
                      ? 'text-slate-400 hover:text-white hover:bg-slate-700'
                      : 'text-slate-500 hover:text-slate-700 hover:bg-gray-100'
                }`}
                title="Toggle reasoning mode"
              >
                <Brain className="w-[18px] h-[18px]" />
              </button>
            )}

            <div className={`w-px h-5 mx-1 ${
              theme === 'dark' ? 'bg-slate-700' : 'bg-gray-200'
            }`} />

            <button
              onClick={() => setUseAgent(!useAgent)}
              disabled={disabled}
              className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed transition-colors ${
                useAgent
                  ? theme === 'dark'
                    ? 'text-emerald-300 bg-emerald-500/15 border border-emerald-500/30'
                    : 'text-emerald-700 bg-emerald-50 border border-emerald-200'
                  : theme === 'dark'
                    ? 'text-slate-400 hover:text-white hover:bg-slate-700'
                    : 'text-slate-500 hover:text-slate-700 hover:bg-gray-100'
              }`}
              title={useAgent ? 'Agent mode ON — MCP tools active' : 'Enable agent mode to use MCP tools'}
            >
              <Bot className="w-[15px] h-[15px]" />
              Agent
            </button>
          </div>

          {/* Right side — processing status + send */}
          <div className="flex items-center gap-2">
            {processingStatus && (
              <span className={`text-xs px-2 py-1 rounded-full font-medium animate-pulse ${
                theme === 'dark' ? 'bg-blue-500/15 text-blue-400' : 'bg-blue-50 text-blue-600'
              }`}>
                {processingStatus}
              </span>
            )}

            <button
              onClick={handleSubmit}
              disabled={disabled || (!input.trim() && attachedFiles.length === 0)}
              className={`p-2 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed transition-all ${
                input.trim() || attachedFiles.length > 0
                  ? theme === 'dark'
                    ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-600/20'
                    : 'bg-blue-500 hover:bg-blue-600 text-white shadow-lg shadow-blue-500/20'
                  : theme === 'dark'
                    ? 'text-slate-600 bg-slate-700/50'
                    : 'text-slate-400 bg-gray-100'
              }`}
              title="Send message"
            >
              {isLoading ? (
                <Loader2 className="w-[18px] h-[18px] animate-spin" />
              ) : (
                <Send className="w-[18px] h-[18px]" />
              )}
            </button>
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_STRING}
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>
    </div>
  )
}
