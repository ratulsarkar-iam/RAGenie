import { useState, useCallback } from 'react'
import ChatInterface from './components/ChatInterface'
import Analytics from './components/Analytics'
import About from './components/About'
import PersonalAssistant from './components/PersonalAssistant'
import NewsPage from './components/NewsPage'
import DatabasePage from './components/DatabasePage'
import MCPServersPage from './components/MCPServersPage'
import Sidebar from './components/Sidebar'
import GenieLogo from './components/GenieLogo'
import SplashScreen from './components/SplashScreen'
import { Sparkles, Moon, Sun, MessageSquare, BarChart3, X, Info, ExternalLink, Brain, Newspaper, DatabaseZap, Plug } from 'lucide-react'
import { useTheme } from './contexts/ThemeContext'
// @ts-ignore - will be installed
import ReactMarkdown from 'react-markdown'

function App() {
  const [showSplash, setShowSplash] = useState(() => {
    return !sessionStorage.getItem('ragenie-splash-shown')
  })
  const [conversationId] = useState('default')
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [activeView, setActiveView] = useState<'chat' | 'analytics' | 'about' | 'assistant' | 'news' | 'database' | 'mcp'>('chat')
  const [refreshDocuments, setRefreshDocuments] = useState(0)
  const [summary, setSummary] = useState<any>(null)
  const { theme, toggleTheme } = useTheme()

  const handleSplashComplete = useCallback(() => {
    sessionStorage.setItem('ragenie-splash-shown', 'true')
    setShowSplash(false)
  }, [])

  const handleDocumentAdded = () => {
    // Trigger refresh in Sidebar by incrementing counter
    setRefreshDocuments(prev => prev + 1)
  }

  const handleSummaryOpen = (summaryData: any) => {
    setSummary(summaryData)
  }

  return (
    <>
    {showSplash && <SplashScreen onComplete={handleSplashComplete} />}
    <div className={`flex h-screen overflow-hidden transition-colors duration-300 ${
      theme === 'dark' 
        ? 'bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900' 
        : 'bg-gradient-to-br from-gray-50 via-blue-50 to-gray-50'
    }`}>
      {/* Professional background pattern */}
      <div className={`absolute inset-0 ${
        theme === 'dark'
          ? 'bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-900/20 via-transparent to-transparent'
          : 'bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-200/30 via-transparent to-transparent'
      }`} />
      <div 
        className="absolute inset-0 opacity-30" 
        style={{ 
          backgroundImage: theme === 'dark'
            ? `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
            : `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='0.02'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
        }} 
      />
      
      <div className="relative flex w-full h-full z-10">
      {/* Sidebar */}
      <Sidebar 
        isOpen={isSidebarOpen} 
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        refreshTrigger={refreshDocuments}
        onSummaryOpen={handleSummaryOpen}
      />

      {/* Main Chat Area */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {/* Header - Professional */}
        <header className={`flex-shrink-0 backdrop-blur-2xl border-b px-6 py-3 shadow-lg transition-colors z-20 ${
          theme === 'dark'
            ? 'bg-slate-900/80 border-slate-700/50'
            : 'bg-white/80 border-gray-200'
        }`}>
          <div className="flex items-center gap-3">
            <GenieLogo size={36} />
            <div className="flex flex-col">
              <h1 className={`text-2xl font-semibold ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>
                RAGenie
              </h1>
              <p className={`text-xs flex items-center gap-1 font-medium ${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>
                <Sparkles className="w-3 h-3" />
                AI Knowledge Assistant
              </p>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <div className="flex gap-2">
                <button
                  onClick={() => setActiveView('chat')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                    activeView === 'chat'
                      ? theme === 'dark'
                        ? 'bg-blue-600 text-white'
                        : 'bg-blue-500 text-white'
                      : theme === 'dark'
                      ? 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                      : 'bg-gray-100 hover:bg-gray-200 text-slate-700'
                  }`}
                >
                  <MessageSquare className="w-4 h-4" />
                  Chat
                </button>
                <button
                  onClick={() => setActiveView('analytics')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                    activeView === 'analytics'
                      ? theme === 'dark'
                        ? 'bg-blue-600 text-white'
                        : 'bg-blue-500 text-white'
                      : theme === 'dark'
                      ? 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                      : 'bg-gray-100 hover:bg-gray-200 text-slate-700'
                  }`}
                >
                  <BarChart3 className="w-4 h-4" />
                  Analytics
                </button>
                <button
                  onClick={() => setActiveView('news')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                    activeView === 'news'
                      ? theme === 'dark'
                        ? 'bg-blue-600 text-white'
                        : 'bg-blue-500 text-white'
                      : theme === 'dark'
                      ? 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                      : 'bg-gray-100 hover:bg-gray-200 text-slate-700'
                  }`}
                >
                  <Newspaper className="w-4 h-4" />
                  News
                </button>
                <button
                  onClick={() => setActiveView('database')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                    activeView === 'database'
                      ? theme === 'dark'
                        ? 'bg-blue-600 text-white'
                        : 'bg-blue-500 text-white'
                      : theme === 'dark'
                      ? 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                      : 'bg-gray-100 hover:bg-gray-200 text-slate-700'
                  }`}
                >
                  <DatabaseZap className="w-4 h-4" />
                  DB Viewer
                </button>
                <button
                  onClick={() => setActiveView('about')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                    activeView === 'about'
                      ? theme === 'dark'
                        ? 'bg-blue-600 text-white'
                        : 'bg-blue-500 text-white'
                      : theme === 'dark'
                      ? 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                      : 'bg-gray-100 hover:bg-gray-200 text-slate-700'
                  }`}
                >
                  <Info className="w-4 h-4" />
                  About
                </button>
                <button
                  onClick={() => setActiveView('mcp')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                    activeView === 'mcp'
                      ? theme === 'dark'
                        ? 'bg-blue-600 text-white'
                        : 'bg-blue-500 text-white'
                      : theme === 'dark'
                      ? 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                      : 'bg-gray-100 hover:bg-gray-200 text-slate-700'
                  }`}
                >
                  <Plug className="w-4 h-4" />
                  MCP Servers
                </button>
                <button
                  onClick={() => setActiveView('assistant')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                    activeView === 'assistant'
                      ? theme === 'dark'
                        ? 'bg-purple-600 text-white'
                        : 'bg-purple-500 text-white'
                      : theme === 'dark'
                      ? 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                      : 'bg-gray-100 hover:bg-gray-200 text-slate-700'
                  }`}
                >
                  <Brain className="w-4 h-4" />
                  Assistant
                </button>
              </div>
              <div className="flex gap-2">
                <a
                  href="http://localhost:8000/docs"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg font-medium transition-all ${
                    theme === 'dark'
                      ? 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                      : 'bg-gray-100 hover:bg-gray-200 text-slate-700'
                  }`}
                  title="API Documentation (Swagger)"
                >
                  <ExternalLink className="w-4 h-4" />
                  API Docs
                </a>
              </div>
              <button
                onClick={toggleTheme}
                className={`p-2 rounded-lg transition-all ${
                  theme === 'dark'
                    ? 'bg-slate-800 hover:bg-slate-700 text-yellow-400'
                    : 'bg-gray-100 hover:bg-gray-200 text-slate-700'
                }`}
                title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              >
                {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
              <span className={`text-xs px-3 py-1.5 backdrop-blur-xl rounded-full border font-medium ${
                theme === 'dark'
                  ? 'text-slate-300 bg-slate-800/50 border-slate-700'
                  : 'text-slate-600 bg-gray-100/50 border-gray-300'
              }`}>
                Powered by Ollama
              </span>
            </div>
          </div>
        </header>

        {/* Main Content — all pages stay mounted; CSS hides inactive ones */}
        <div className={`flex-1 min-w-0 overflow-hidden flex flex-col ${activeView === 'chat'      ? '' : 'hidden'}`}><ChatInterface conversationId={conversationId} /></div>
        <div className={`flex-1 min-w-0 overflow-hidden flex flex-col ${activeView === 'analytics'  ? '' : 'hidden'}`}><Analytics onDocumentAdded={handleDocumentAdded} /></div>
        <div className={`flex-1 min-w-0 overflow-hidden flex flex-col ${activeView === 'assistant'  ? '' : 'hidden'}`}><PersonalAssistant /></div>
        <div className={`flex-1 min-w-0 overflow-hidden flex flex-col ${activeView === 'news'       ? '' : 'hidden'}`}><NewsPage /></div>
        <div className={`flex-1 min-w-0 overflow-hidden flex flex-col ${activeView === 'database'   ? '' : 'hidden'}`}><DatabasePage /></div>
        <div className={`flex-1 min-w-0 overflow-hidden flex flex-col ${activeView === 'mcp'        ? '' : 'hidden'}`}><MCPServersPage /></div>
        <div className={`flex-1 min-w-0 overflow-hidden flex flex-col ${activeView === 'about'      ? '' : 'hidden'}`}><About /></div>
      </div>

      {/* Summary Full-Screen Modal - Centered in Chat Area */}
      {summary && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className={`w-full h-full max-w-6xl max-h-[90vh] rounded-2xl shadow-2xl overflow-hidden ${
            theme === 'dark' ? 'bg-slate-900' : 'bg-white'
          }`}>
            {/* Modal Header */}
            <div className={`px-8 py-5 border-b flex items-center justify-between ${
              theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-gray-50 border-gray-200'
            }`}>
              <div>
                <h2 className={`text-2xl font-bold ${
                  theme === 'dark' ? 'text-white' : 'text-slate-900'
                }`}>
                  Document Summary
                </h2>
                <p className={`text-sm mt-1 ${
                  theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                }`}>
                  {summary.filename}
                </p>
              </div>
              <button
                onClick={() => setSummary(null)}
                className={`p-2 rounded-lg transition-all ${
                  theme === 'dark' ? 'hover:bg-slate-700 text-slate-300' : 'hover:bg-gray-200 text-slate-700'
                }`}
                title="Close"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            
            {/* Modal Content */}
            <div className="h-[calc(100%-89px)] overflow-y-auto p-8">
              {/* Metadata Cards */}
              <div className="grid grid-cols-2 gap-6 mb-8">
                <div className={`p-6 rounded-xl ${
                  theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-gray-50 border border-gray-200'
                }`}>
                  <p className={`text-sm font-medium mb-2 ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>File Type</p>
                  <p className={`text-2xl font-bold ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>{summary.file_type.toUpperCase()}</p>
                </div>
                <div className={`p-6 rounded-xl ${
                  theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-gray-50 border border-gray-200'
                }`}>
                  <p className={`text-sm font-medium mb-2 ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>Chunks</p>
                  <p className={`text-2xl font-bold ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>{summary.num_chunks}</p>
                </div>
              </div>

              {/* Keywords */}
              {summary.keywords && summary.keywords.length > 0 && (
                <div className="mb-8">
                  <h3 className={`text-lg font-semibold mb-4 ${
                    theme === 'dark' ? 'text-slate-200' : 'text-slate-800'
                  }`}>Keywords</h3>
                  <div className="flex flex-wrap gap-3">
                    {summary.keywords.map((kw: any, idx: number) => (
                      <span
                        key={idx}
                        className={`px-4 py-2 rounded-full text-sm font-medium ${
                          theme === 'dark'
                            ? 'bg-purple-900/50 text-purple-200 border border-purple-800'
                            : 'bg-purple-100 text-purple-800 border border-purple-200'
                        }`}
                      >
                        {kw.word}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Summary Content */}
              {summary.preview && (
                <div>
                  <h3 className={`text-lg font-semibold mb-4 ${
                    theme === 'dark' ? 'text-slate-200' : 'text-slate-800'
                  }`}>Summary</h3>
                  <div className={`p-8 rounded-xl ${
                    theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-gray-50 border border-gray-200'
                  }`}>
                    <div className={`prose prose-lg max-w-none ${
                      theme === 'dark' 
                        ? 'prose-invert prose-headings:text-slate-200 prose-p:text-slate-300 prose-a:text-purple-400 prose-strong:text-slate-200 prose-code:text-slate-300 prose-li:text-slate-300' 
                        : 'prose-headings:text-slate-900 prose-p:text-slate-700 prose-a:text-purple-600 prose-strong:text-slate-900 prose-code:text-slate-700 prose-li:text-slate-700'
                    }`}>
                      <ReactMarkdown>{summary.preview}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
    </>
  )
}

export default App
