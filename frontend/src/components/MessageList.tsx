import ReactMarkdown from 'react-markdown'
import { User, Brain } from 'lucide-react'
import GenieLogo from './GenieLogo'
import { useTheme } from '../contexts/ThemeContext'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  useReasoning?: boolean
}

interface MessageListProps {
  messages: Message[]
  streamingContent?: string
}

export default function MessageList({ messages, streamingContent = '' }: MessageListProps) {
  const { theme } = useTheme()
  
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
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.useReasoning && (
                  <div className="flex items-center gap-1 mt-2 text-xs opacity-80">
                    <Brain className="w-3 h-3" />
                    <span>Reasoning mode</span>
                  </div>
                )}
              </div>
            ) : (
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
            )}
            <div className="text-xs opacity-60 mt-2">
              {new Date(message.timestamp).toLocaleTimeString()}
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
