import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { User, Brain, FileText, Image, Music, FileSpreadsheet, ThumbsUp, ThumbsDown, Wrench, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react'
import GenieLogo from './GenieLogo'
import { useTheme } from '../contexts/ThemeContext'
import type { FileAttachment, ToolCallEvent } from './ChatInterface'
import { submitFeedback } from '../api/assistant'

function getAttachmentIcon(fileType: string) {
  if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'svg'].includes(fileType)) return Image
  if (['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma'].includes(fileType)) return Music
  if (['xlsx', 'xls', 'csv'].includes(fileType)) return FileSpreadsheet
  return FileText
}

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function ToolCallBubble({ ev }: { ev: ToolCallEvent }) {
  const { theme } = useTheme()
  const [open, setOpen] = useState(false)
  const isError = Boolean(ev.error)
  return (
    <div className={`rounded-lg border text-xs overflow-hidden mb-2 ${
      isError
        ? theme === 'dark' ? 'bg-red-900/20 border-red-500/30' : 'bg-red-50 border-red-200'
        : theme === 'dark' ? 'bg-slate-700/60 border-slate-600' : 'bg-gray-50 border-gray-200'
    }`}>
      <button onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:opacity-80 transition-opacity">
        {isError
          ? <AlertCircle className="w-3 h-3 text-red-400 flex-shrink-0" />
          : <Wrench className="w-3 h-3 text-blue-400 flex-shrink-0" />}
        <code className={`font-mono font-medium ${isError ? 'text-red-400' : 'text-blue-400'}`}>{ev.tool}</code>
        {!open && !isError && ev.result && (
          <span className={`ml-2 truncate max-w-[200px] ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>
            → {ev.result.slice(0, 60)}
          </span>
        )}
        <span className={`ml-auto flex-shrink-0 ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>
          {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </span>
      </button>
      {open && (
        <div className={`border-t px-3 py-2 space-y-2 ${theme === 'dark' ? 'border-slate-600' : 'border-gray-200'}`}>
          {ev.args && (
            <div>
              <p className={`text-xs font-medium mb-1 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Input</p>
              <pre className={`text-xs font-mono whitespace-pre-wrap break-all rounded p-2 ${
                theme === 'dark' ? 'bg-slate-900 text-slate-300' : 'bg-white text-slate-700 border border-gray-200'
              }`}>{ev.args}</pre>
            </div>
          )}
          {ev.error ? (
            <div>
              <p className="text-xs font-medium mb-1 text-red-400">Error</p>
              <pre className={`text-xs font-mono whitespace-pre-wrap break-all rounded p-2 ${
                theme === 'dark' ? 'bg-red-900/30 text-red-300' : 'bg-red-50 text-red-700 border border-red-200'
              }`}>{ev.error}</pre>
            </div>
          ) : ev.result ? (
            <div>
              <p className={`text-xs font-medium mb-1 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Result</p>
              <pre className={`text-xs font-mono whitespace-pre-wrap break-all rounded p-2 max-h-48 overflow-y-auto ${
                theme === 'dark' ? 'bg-slate-900 text-emerald-300' : 'bg-white text-emerald-700 border border-gray-200'
              }`}>{ev.result}</pre>
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  useReasoning?: boolean
  attachments?: FileAttachment[]
  toolCalls?: ToolCallEvent[]
}

interface MessageListProps {
  messages: Message[]
  streamingContent?: string
}

export default function MessageList({ messages, streamingContent = '' }: MessageListProps) {
  const { theme } = useTheme()
  const [feedbackSent, setFeedbackSent] = useState<Record<number, 'thumbs_up' | 'thumbs_down'>>({})

  const handleFeedback = async (index: number, rating: 'thumbs_up' | 'thumbs_down') => {
    if (feedbackSent[index]) return
    setFeedbackSent(prev => ({ ...prev, [index]: rating }))
    try {
      await submitFeedback('explicit', rating, `msg-${index}`)
    } catch {
      // silent — feedback is best-effort
    }
  }
  
  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {messages.map((message, index) => (
        <div
          key={index}
          className={`flex gap-4 ${
            message.role === 'user' ? 'justify-end' : 'justify-start'
          }`}
        >
          {message.role === 'assistant' && (
            <div className={`flex-shrink-0 w-10 h-10 rounded-full backdrop-blur-xl border flex items-center justify-center shadow-lg ${
              theme === 'dark'
                ? 'bg-slate-800 border-slate-700'
                : 'bg-white border-gray-200'
            }`}>
              <GenieLogo size={28} />
            </div>
          )}
          
          <div
            className={`flex-1 max-w-3xl rounded-2xl p-4 backdrop-blur-xl shadow-lg ${
              message.role === 'user'
                ? theme === 'dark'
                  ? 'bg-blue-600 text-white ml-12 border border-blue-500'
                  : 'bg-blue-500 text-white ml-12 border border-blue-400'
                : theme === 'dark'
                  ? 'bg-slate-800/80 text-white border border-slate-700'
                  : 'bg-white text-slate-900 border border-gray-200'
            }`}
          >
            {message.role === 'user' ? (
              <div>
                {message.attachments && message.attachments.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {message.attachments.map((att, i) => {
                      const Icon = getAttachmentIcon(att.file_type)
                      return (
                        <span
                          key={att.filename + i}
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs bg-white/20 backdrop-blur-sm"
                        >
                          <Icon className="w-3 h-3" />
                          <span className="truncate max-w-[120px]">{att.filename}</span>
                          <span className="opacity-70">({formatFileSize(att.file_size)})</span>
                        </span>
                      )
                    })}
                  </div>
                )}
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.useReasoning && (
                  <div className="flex items-center gap-1 mt-2 text-xs opacity-80">
                    <Brain className="w-3 h-3" />
                    <span>Reasoning mode</span>
                  </div>
                )}
              </div>
            ) : (
              <div>
              {message.toolCalls && message.toolCalls.length > 0 && (
                <div className="mb-3">
                  {message.toolCalls.map((ev, i) => <ToolCallBubble key={i} ev={ev} />)}
                </div>
              )}
              <div className={`prose max-w-none ${
                theme === 'dark' ? 'prose-invert' : 'prose-slate'
              }`}>
                <ReactMarkdown
                  components={{
                    // Links
                    a: ({ node, ...props }) => (
                      <a
                        {...props}
                        className="text-blue-400 hover:text-blue-300 underline"
                        target="_blank"
                        rel="noopener noreferrer"
                      />
                    ),
                    // Code blocks
                    code: ({ node, inline, ...props }: any) =>
                      inline ? (
                        <code
                          {...props}
                          className={`px-1.5 py-0.5 rounded font-mono text-sm ${
                            theme === 'dark'
                              ? 'bg-slate-700 text-pink-300'
                              : 'bg-gray-100 text-pink-600'
                          }`}
                        />
                      ) : (
                        <code
                          {...props}
                          className={`block p-3 rounded-lg font-mono text-sm overflow-x-auto ${
                            theme === 'dark'
                              ? 'bg-slate-900 text-gray-100'
                              : 'bg-gray-50 text-gray-900'
                          }`}
                        />
                      ),
                    // Headings
                    h1: ({ node, ...props }) => (
                      <h1 {...props} className="text-2xl font-bold mt-4 mb-2" />
                    ),
                    h2: ({ node, ...props }) => (
                      <h2 {...props} className="text-xl font-bold mt-3 mb-2" />
                    ),
                    h3: ({ node, ...props }) => (
                      <h3 {...props} className="text-lg font-semibold mt-3 mb-1" />
                    ),
                    // Lists
                    ul: ({ node, ...props }) => (
                      <ul {...props} className="list-disc list-inside space-y-1 my-2" />
                    ),
                    ol: ({ node, ...props }) => (
                      <ol {...props} className="list-decimal list-inside space-y-1 my-2" />
                    ),
                    // Blockquotes
                    blockquote: ({ node, ...props }) => (
                      <blockquote
                        {...props}
                        className={`border-l-4 pl-4 italic my-2 ${
                          theme === 'dark'
                            ? 'border-blue-500 text-slate-300'
                            : 'border-blue-400 text-slate-600'
                        }`}
                      />
                    ),
                    // Paragraphs
                    p: ({ node, ...props }) => (
                      <p {...props} className="my-2 leading-relaxed" />
                    ),
                    // Strong (bold)
                    strong: ({ node, ...props }) => (
                      <strong {...props} className="font-bold" />
                    ),
                    // Emphasis (italic)
                    em: ({ node, ...props }) => (
                      <em {...props} className="italic" />
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
              </div>
            )}
            <div className="flex items-center justify-between mt-2">
              <span className="text-xs opacity-60">
                {new Date(message.timestamp).toLocaleTimeString()}
              </span>
              {message.role === 'assistant' && (
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => handleFeedback(index, 'thumbs_up')}
                    disabled={!!feedbackSent[index]}
                    title="Good response"
                    className={`p-1 rounded-lg transition-all disabled:cursor-default ${
                      feedbackSent[index] === 'thumbs_up'
                        ? 'text-green-400'
                        : theme === 'dark'
                        ? 'text-slate-500 hover:text-green-400 hover:bg-slate-700'
                        : 'text-slate-400 hover:text-green-500 hover:bg-gray-100'
                    }`}
                  >
                    <ThumbsUp className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleFeedback(index, 'thumbs_down')}
                    disabled={!!feedbackSent[index]}
                    title="Poor response"
                    className={`p-1 rounded-lg transition-all disabled:cursor-default ${
                      feedbackSent[index] === 'thumbs_down'
                        ? 'text-red-400'
                        : theme === 'dark'
                        ? 'text-slate-500 hover:text-red-400 hover:bg-slate-700'
                        : 'text-slate-400 hover:text-red-500 hover:bg-gray-100'
                    }`}
                  >
                    <ThumbsDown className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>
          </div>

          {message.role === 'user' && (
            <div className={`flex-shrink-0 w-10 h-10 rounded-full backdrop-blur-xl border flex items-center justify-center shadow-lg ${
              theme === 'dark'
                ? 'bg-blue-600 border-blue-500'
                : 'bg-blue-500 border-blue-400'
            }`}>
              <User className="w-5 h-5 text-white" />
            </div>
          )}
        </div>
      ))}
      
      {/* Streaming message */}
      {streamingContent && (
        <div className="flex gap-4 justify-start">
          <div className={`flex-shrink-0 w-10 h-10 rounded-full backdrop-blur-xl border flex items-center justify-center shadow-lg ${
            theme === 'dark'
              ? 'bg-slate-800 border-slate-700'
              : 'bg-white border-gray-200'
          }`}>
            <GenieLogo size={28} />
          </div>
          
          <div className={`flex-1 max-w-3xl rounded-2xl p-4 backdrop-blur-xl shadow-lg ${
            theme === 'dark'
              ? 'bg-slate-800/80 text-white border border-slate-700'
              : 'bg-white text-slate-900 border border-gray-200'
          }`}>
            <div className={`prose max-w-none ${
              theme === 'dark' ? 'prose-invert' : 'prose-slate'
            }`}>
              <ReactMarkdown
                components={{
                  // Links
                  a: ({ node, ...props }) => (
                    <a
                      {...props}
                      className="text-blue-400 hover:text-blue-300 underline"
                      target="_blank"
                      rel="noopener noreferrer"
                    />
                  ),
                  // Code blocks
                  code: ({ node, inline, ...props }: any) =>
                    inline ? (
                      <code
                        {...props}
                        className={`px-1.5 py-0.5 rounded font-mono text-sm ${
                          theme === 'dark'
                            ? 'bg-slate-700 text-pink-300'
                            : 'bg-gray-100 text-pink-600'
                        }`}
                      />
                    ) : (
                      <code
                        {...props}
                        className={`block p-3 rounded-lg font-mono text-sm overflow-x-auto ${
                          theme === 'dark'
                            ? 'bg-slate-900 text-gray-100'
                            : 'bg-gray-50 text-gray-900'
                        }`}
                      />
                    ),
                  // Headings
                  h1: ({ node, ...props }) => (
                    <h1 {...props} className="text-2xl font-bold mt-4 mb-2" />
                  ),
                  h2: ({ node, ...props }) => (
                    <h2 {...props} className="text-xl font-bold mt-3 mb-2" />
                  ),
                  h3: ({ node, ...props }) => (
                    <h3 {...props} className="text-lg font-semibold mt-3 mb-1" />
                  ),
                  // Lists
                  ul: ({ node, ...props }) => (
                    <ul {...props} className="list-disc list-inside space-y-1 my-2" />
                  ),
                  ol: ({ node, ...props }) => (
                    <ol {...props} className="list-decimal list-inside space-y-1 my-2" />
                  ),
                  // Blockquotes
                  blockquote: ({ node, ...props }) => (
                    <blockquote
                      {...props}
                      className={`border-l-4 pl-4 italic my-2 ${
                        theme === 'dark'
                          ? 'border-blue-500 text-slate-300'
                          : 'border-blue-400 text-slate-600'
                      }`}
                    />
                  ),
                  // Paragraphs
                  p: ({ node, ...props }) => (
                    <p {...props} className="my-2 leading-relaxed" />
                  ),
                  // Strong (bold)
                  strong: ({ node, ...props }) => (
                    <strong {...props} className="font-bold" />
                  ),
                  // Emphasis (italic)
                  em: ({ node, ...props }) => (
                    <em {...props} className="italic" />
                  ),
                }}
              >
                {streamingContent}
              </ReactMarkdown>
            </div>
            <div className="flex items-center gap-2 text-xs opacity-60 mt-2">
              <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>
              Typing...
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
