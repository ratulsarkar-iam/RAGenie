import { useState, useRef, useEffect, useCallback } from 'react'
import MessageList from './MessageList'
import MessageInput from './MessageInput'
import SearchHistoryPanel from './SearchHistoryPanel'
import GenieLogo from './GenieLogo'
import { ChatWebSocket } from '../api/websocket'
import { Sparkles, BookOpen, Search } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import { useSearchHistory } from '../hooks/useSearchHistory'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface ChatInterfaceProps {
  conversationId: string
}

export default function ChatInterface({ conversationId }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [processingStatus, setProcessingStatus] = useState<string>('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<ChatWebSocket | null>(null)
  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [pendingHistoryQuery, setPendingHistoryQuery] = useState<string | null>(null)
  const { theme } = useTheme()
  const {
    history: searchHistory,
    addToHistory,
    removeFromHistory,
    clearHistory: clearSearchHistory,
  } = useSearchHistory()

  const handleToggleHistory = useCallback(() => {
    setIsHistoryOpen(prev => !prev)
  }, [])

  const handleHistorySelect = useCallback((query: string) => {
    setPendingHistoryQuery(query)
  }, [])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingContent])

  // Initialize WebSocket connection
  useEffect(() => {
    // Prevent double initialization in React StrictMode
    if (wsRef.current?.isConnected()) {
      return
    }

    const ws = new ChatWebSocket()
    wsRef.current = ws

    ws.connect().catch(err => {
      console.error('Failed to connect WebSocket:', err)
    })

    ws.onMessage((message) => {
      console.log('Received WebSocket message:', message.type, message.content ? `${message.content.substring(0, 50)}...` : 'no content')
      switch (message.type) {
        case 'stream_start':
          setStreamingContent('')
          setIsLoading(true)
          setProcessingStatus('Thinking...')
          break

        case 'stream_token':
          if (message.content) {
            setStreamingContent(prev => prev + message.content)
            if (processingStatus === 'Reasoning...') {
              setProcessingStatus('Generating response...')
            }
          }
          break

        case 'stream_end':
          if (message.content) {
            const assistantMessage: Message = {
              role: 'assistant',
              content: message.content,
              timestamp: new Date().toISOString()
            }
            setMessages(prev => [...prev, assistantMessage])
          }
          setStreamingContent('')
          setProcessingStatus('')
          setIsLoading(false)
          break

        case 'assistant_message':
          if (message.content) {
            const assistantMessage: Message = {
              role: 'assistant',
              content: message.content,
              timestamp: new Date().toISOString()
            }
            setMessages(prev => [...prev, assistantMessage])
          }
          setProcessingStatus('')
          setIsLoading(false)
          break

        case 'reasoning':
          // Update status but don't show reasoning as separate message
          setProcessingStatus('Reasoning...')
          break

        case 'error':
          const errorMessage: Message = {
            role: 'assistant',
            content: message.content || 'Sorry, I encountered an error. Please try again.',
            timestamp: new Date().toISOString()
          }
          setMessages(prev => [...prev, errorMessage])
          setStreamingContent('')
          setProcessingStatus('')
          setIsLoading(false)
          break
      }
    })

    return () => {
      // Only disconnect if this is the actual unmount (not StrictMode remount)
      setTimeout(() => {
        if (wsRef.current === ws) {
          ws.disconnect()
        }
      }, 100)
    }
  }, [])

  const handleSendMessage = async (content: string, useReasoning: boolean = false) => {
    if (!wsRef.current || !wsRef.current.isConnected()) {
      console.error('WebSocket not connected')
      return
    }

    // Save to search history
    addToHistory(content)

    // Add user message
    const userMessage: Message = {
      role: 'user',
      content,
      timestamp: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMessage])

    try {
      // Send via WebSocket with reasoning flag
      wsRef.current.sendMessage(content, conversationId, false, useReasoning)
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
      setIsLoading(false)
    }
  }

  const handleClearHistory = () => {
    setMessages([])
  }

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Chat Column */}
      <div className="flex-1 flex flex-col overflow-hidden">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-2xl mx-auto">
              <div className="mb-6 flex justify-center">
                <div className="relative">
                  <GenieLogo size={120} />
                  <div className="absolute -top-2 -right-2 animate-bounce">
                    <Sparkles className="w-6 h-6 text-yellow-400" />
                  </div>
                </div>
              </div>
              <h2 className={`text-3xl font-bold mb-3 ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>
                Welcome to RAGenie!
              </h2>
              <p className={`mb-8 ${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>
                Your magical AI assistant ready to answer questions from your knowledge base
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
                <div className={`backdrop-blur-xl border rounded-2xl p-6 hover:shadow-xl transition-all ${
                  theme === 'dark'
                    ? 'bg-slate-800/50 border-slate-700 hover:bg-slate-800'
                    : 'bg-white border-gray-200 hover:bg-gray-50'
                }`}>
                  <BookOpen className={`w-8 h-8 mb-3 mx-auto ${
                    theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
                  }`} />
                  <h3 className={`font-semibold mb-2 ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>Document Knowledge</h3>
                  <p className={`text-sm ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>
                    Ask questions about your uploaded documents and get instant answers
                  </p>
                </div>
                
                <div className={`backdrop-blur-xl border rounded-2xl p-6 hover:shadow-xl transition-all ${
                  theme === 'dark'
                    ? 'bg-slate-800/50 border-slate-700 hover:bg-slate-800'
                    : 'bg-white border-gray-200 hover:bg-gray-50'
                }`}>
                  <Search className={`w-8 h-8 mb-3 mx-auto ${
                    theme === 'dark' ? 'text-purple-400' : 'text-purple-600'
                  }`} />
                  <h3 className={`font-semibold mb-2 ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>Web Search</h3>
                  <p className={`text-sm ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>
                    Search the internet for the latest information when needed
                  </p>
                </div>
              </div>
              
              <p className={`text-sm mt-8 font-medium ${
                theme === 'dark' ? 'text-slate-500' : 'text-slate-500'
              }`}>
                💡 Tip: Upload documents using the sidebar to expand my knowledge!
              </p>
            </div>
          </div>
        ) : (
          <>
            <MessageList messages={messages} streamingContent={streamingContent} />
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Area */}
      <MessageInput 
        onSendMessage={handleSendMessage}
        onClearHistory={handleClearHistory}
        isLoading={isLoading}
        disabled={isLoading}
        processingStatus={processingStatus}
        isHistoryOpen={isHistoryOpen}
        onToggleHistory={handleToggleHistory}
        hasHistory={searchHistory.length > 0}
        pendingQuery={pendingHistoryQuery}
        onPendingQueryConsumed={() => setPendingHistoryQuery(null)}
      />
      </div>

      {/* Search History Pane */}
      {isHistoryOpen && (
        <SearchHistoryPanel
          history={searchHistory}
          onSelect={handleHistorySelect}
          onRemove={removeFromHistory}
          onClear={clearSearchHistory}
          onClose={() => setIsHistoryOpen(false)}
        />
      )}
    </div>
  )
}
