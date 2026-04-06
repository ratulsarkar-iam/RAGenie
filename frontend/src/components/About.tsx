import { useTheme } from '../contexts/ThemeContext'
import { Sparkles, BookOpen, BarChart3, Shield, Zap, Database, Globe, Brain, Code } from 'lucide-react'
import GenieLogo from './GenieLogo'

function About() {
  const { theme } = useTheme()

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-8 py-12">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <div className="flex justify-center mb-6">
            <GenieLogo size={80} />
          </div>
          <h1 className={`text-5xl font-bold mb-4 ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>
            RAGenie
          </h1>
          <p className={`text-xl mb-2 ${
            theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
          }`}>
            Intelligent RAG Chatbot with Analytics
          </p>
          <p className={`text-lg ${
            theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
          }`}>
            Your personal AI that knows your documents, searches the web, and analyzes your data
          </p>
        </div>

        {/* What It Is */}
        <section className="mb-12">
          <h2 className={`text-3xl font-bold mb-6 ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>
            What It Is
          </h2>
          <div className={`p-6 rounded-xl ${
            theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
          }`}>
            <p className={`text-lg leading-relaxed ${
              theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
            }`}>
              RAGenie is a <strong>personal AI assistant</strong> that combines your private documents with real-time internet search and advanced analytics capabilities. It's like having ChatGPT, but with access to your own knowledge base and data analysis tools.
            </p>
          </div>
        </section>

        {/* Core Purpose */}
        <section className="mb-12">
          <h2 className={`text-3xl font-bold mb-6 ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>
            Core Purpose
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className={`p-6 rounded-xl ${
              theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
            }`}>
              <BookOpen className={`w-8 h-8 mb-3 ${
                theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
              }`} />
              <h3 className={`text-lg font-semibold mb-2 ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>
                Learn from your documents
              </h3>
              <p className={`${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>
                Upload PDFs, text files, and markdown documents to create a searchable knowledge base
              </p>
            </div>

            <div className={`p-6 rounded-xl ${
              theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
            }`}>
              <Brain className={`w-8 h-8 mb-3 ${
                theme === 'dark' ? 'text-purple-400' : 'text-purple-600'
              }`} />
              <h3 className={`text-lg font-semibold mb-2 ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>
                Answer questions intelligently
              </h3>
              <p className={`${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>
                Uses AI to retrieve relevant information from your documents and the internet
              </p>
            </div>

            <div className={`p-6 rounded-xl ${
              theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
            }`}>
              <BarChart3 className={`w-8 h-8 mb-3 ${
                theme === 'dark' ? 'text-green-400' : 'text-green-600'
              }`} />
              <h3 className={`text-lg font-semibold mb-2 ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>
                Analyze data
              </h3>
              <p className={`${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>
                Built-in analytics engine for exploring datasets, generating visualizations, and extracting insights
              </p>
            </div>

            <div className={`p-6 rounded-xl ${
              theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
            }`}>
              <Shield className={`w-8 h-8 mb-3 ${
                theme === 'dark' ? 'text-orange-400' : 'text-orange-600'
              }`} />
              <h3 className={`text-lg font-semibold mb-2 ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>
                Privacy-focused
              </h3>
              <p className={`${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>
                Runs locally on your machine with optional cloud LLM support
              </p>
            </div>
          </div>
        </section>

        {/* Key Capabilities */}
        <section className="mb-12">
          <h2 className={`text-3xl font-bold mb-6 ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>
            Key Capabilities
          </h2>
          
          <div className="space-y-6">
            {/* Intelligent Chat */}
            <div className={`p-6 rounded-xl ${
              theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
            }`}>
              <div className="flex items-start gap-4">
                <Sparkles className={`w-6 h-6 mt-1 ${
                  theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
                }`} />
                <div className="flex-1">
                  <h3 className={`text-xl font-semibold mb-3 ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>
                    💬 Intelligent Chat
                  </h3>
                  <ul className={`space-y-2 ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>
                    <li>• Multi-model AI support (Ollama local models + optional cloud providers)</li>
                    <li>• Conversation memory and context awareness</li>
                    <li>• Real-time streaming responses via WebSocket</li>
                    <li>• Agent mode for complex multi-step reasoning</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Document Intelligence */}
            <div className={`p-6 rounded-xl ${
              theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
            }`}>
              <div className="flex items-start gap-4">
                <Database className={`w-6 h-6 mt-1 ${
                  theme === 'dark' ? 'text-purple-400' : 'text-purple-600'
                }`} />
                <div className="flex-1">
                  <h3 className={`text-xl font-semibold mb-3 ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>
                    📚 Document Intelligence (RAG)
                  </h3>
                  <ul className={`space-y-2 ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>
                    <li>• Upload and index documents (PDF, TXT, Markdown)</li>
                    <li>• Page-based chunking with BM25 search</li>
                    <li>• Automatic document summarization</li>
                    <li>• Keyword extraction</li>
                    <li>• Ask questions about your documents naturally</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Internet Search */}
            <div className={`p-6 rounded-xl ${
              theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
            }`}>
              <div className="flex items-start gap-4">
                <Globe className={`w-6 h-6 mt-1 ${
                  theme === 'dark' ? 'text-green-400' : 'text-green-600'
                }`} />
                <div className="flex-1">
                  <h3 className={`text-xl font-semibold mb-3 ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>
                    🔍 Internet Search Integration
                  </h3>
                  <ul className={`space-y-2 ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>
                    <li>• DuckDuckGo search built-in (no API keys needed)</li>
                    <li>• Combines web results with document knowledge</li>
                    <li>• Cached results for performance</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Analytics Engine */}
            <div className={`p-6 rounded-xl ${
              theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
            }`}>
              <div className="flex items-start gap-4">
                <BarChart3 className={`w-6 h-6 mt-1 ${
                  theme === 'dark' ? 'text-orange-400' : 'text-orange-600'
                }`} />
                <div className="flex-1">
                  <h3 className={`text-xl font-semibold mb-3 ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>
                    📊 Analytics Engine
                  </h3>
                  <ul className={`space-y-2 ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>
                    <li>• Upload CSV/Excel datasets</li>
                    <li>• Automated exploratory data analysis (EDA)</li>
                    <li>• Generate interactive visualizations (Plotly)</li>
                    <li>• Statistical summaries and insights</li>
                    <li>• Column profiling and data quality checks</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Modern Web Interface */}
            <div className={`p-6 rounded-xl ${
              theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
            }`}>
              <div className="flex items-start gap-4">
                <Zap className={`w-6 h-6 mt-1 ${
                  theme === 'dark' ? 'text-yellow-400' : 'text-yellow-600'
                }`} />
                <div className="flex-1">
                  <h3 className={`text-xl font-semibold mb-3 ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>
                    🎨 Modern Web Interface
                  </h3>
                  <ul className={`space-y-2 ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>
                    <li>• macOS-inspired design with dark/light themes</li>
                    <li>• Real-time chat with markdown rendering</li>
                    <li>• Document management dashboard</li>
                    <li>• Analytics workspace with interactive charts</li>
                    <li>• Responsive and mobile-friendly</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Technical Highlights */}
        <section className="mb-12">
          <h2 className={`text-3xl font-bold mb-6 ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>
            Technical Highlights
          </h2>
          <div className={`p-6 rounded-xl ${
            theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
          }`}>
            <div className="flex items-start gap-4 mb-4">
              <Code className={`w-6 h-6 mt-1 ${
                theme === 'dark' ? 'text-blue-400' : 'text-blue-600'
              }`} />
              <div className="flex-1">
                <ul className={`space-y-2 ${
                  theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                }`}>
                  <li><strong>Backend:</strong> Python FastAPI with async support</li>
                  <li><strong>Frontend:</strong> React + TypeScript + TailwindCSS</li>
                  <li><strong>AI Models:</strong> Supports Ollama (local), HuggingFace, and multi-model configurations</li>
                  <li><strong>Optimized for:</strong> Mac M3 (MPS), but works on CUDA/CPU too</li>
                  <li><strong>Deployment:</strong> Can run fully local or with cloud LLMs</li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Use Cases */}
        <section className="mb-12">
          <h2 className={`text-3xl font-bold mb-6 ${
            theme === 'dark' ? 'text-white' : 'text-slate-900'
          }`}>
            Use Cases
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              'Research assistant for academic papers',
              'Personal knowledge management',
              'Data exploration and visualization',
              'Technical documentation Q&A',
              'Business intelligence on your datasets'
            ].map((useCase, idx) => (
              <div
                key={idx}
                className={`p-4 rounded-lg ${
                  theme === 'dark' ? 'bg-slate-800 border border-slate-700' : 'bg-white border border-gray-200'
                }`}
              >
                <p className={`${
                  theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
                }`}>
                  • {useCase}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Footer */}
        <div className={`text-center pt-8 border-t ${
          theme === 'dark' ? 'border-slate-700' : 'border-gray-200'
        }`}>
          <p className={`text-lg font-medium ${
            theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
          }`}>
            "Your personal AI that knows your documents, searches the web, and analyzes your data - all in one beautiful interface."
          </p>
          <p className={`mt-4 text-sm ${
            theme === 'dark' ? 'text-slate-500' : 'text-slate-500'
          }`}>
            Version 1.0.0 • Built with ❤️ using React, FastAPI, and Ollama
          </p>
        </div>
      </div>
    </div>
  )
}

export default About
