import { useState, useEffect } from 'react'
import { FileText, ChevronLeft, ChevronRight, Database, Trash2, Sparkles, FileSpreadsheet, Loader2 } from 'lucide-react'
import { getDocuments, getHealth, deleteDocument, summarizeDocument } from '../api/chat'
import DocumentUpload from './DocumentUpload'
import GenieLogo from './GenieLogo'
import { useTheme } from '../contexts/ThemeContext'

interface Document {
  doc_id: string
  filename: string
  file_type: string
  file_size: number
  num_chunks: number
}

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
  refreshTrigger?: number
  onSummaryOpen?: (summary: any) => void
}

export default function Sidebar({ isOpen, onToggle, refreshTrigger, onSummaryOpen }: SidebarProps) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [stats, setStats] = useState({ num_documents: 0, num_chunks: 0 })
  const [summarizing, setSummarizing] = useState<string | null>(null)
  const { theme } = useTheme()

  useEffect(() => {
    loadData()
  }, [])

  // Auto-refresh when refreshTrigger changes (e.g., after Analytics upload)
  useEffect(() => {
    if (refreshTrigger !== undefined && refreshTrigger > 0) {
      loadData()
    }
  }, [refreshTrigger])

  const loadData = async () => {
    try {
      const [docs, health] = await Promise.all([getDocuments(), getHealth()])
      setDocuments(docs)
      setStats({ num_documents: health.num_documents, num_chunks: health.num_chunks })
    } catch (error) {
      console.error('Error loading sidebar data:', error)
    }
  }

  const handleDelete = async (docId: string, filename: string) => {
    if (!confirm(`Delete "${filename}"?`)) return
    
    try {
      await deleteDocument(docId)
      await loadData()
    } catch (error) {
      console.error('Error deleting document:', error)
      alert('Failed to delete document')
    }
  }

  const handleSummarize = async (docId: string) => {
    setSummarizing(docId)
    try {
      const result = await summarizeDocument(docId)
      if (onSummaryOpen) {
        onSummaryOpen(result.summary)
      }
    } catch (error) {
      console.error('Error summarizing document:', error)
      alert('Failed to summarize document')
    } finally {
      setSummarizing(null)
    }
  }

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="fixed left-0 top-1/2 -translate-y-1/2 bg-gray-800 p-2 rounded-r-lg hover:bg-gray-700 transition-colors z-50"
      >
        <ChevronRight className="w-5 h-5" />
      </button>
    )
  }

  return (
    <div className={`w-80 backdrop-blur-2xl border-r flex flex-col shadow-2xl transition-colors ${
      theme === 'dark'
        ? 'bg-slate-900/80 border-slate-700/50'
        : 'bg-white/80 border-gray-200'
    }`}>
      {/* Header */}
      <div className={`p-4 border-b flex items-center justify-between ${
        theme === 'dark' ? 'border-slate-700/50' : 'border-gray-200'
      }`}>
        <div className="flex items-center gap-2">
          <GenieLogo size={24} />
          <div>
            <h2 className={`text-lg font-semibold ${
              theme === 'dark' ? 'text-white' : 'text-slate-900'
            }`}>Knowledge Base</h2>
            <p className={`text-xs flex items-center gap-1 font-medium ${
              theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
            }`}>
              <Sparkles className="w-3 h-3" />
              RAGenie
            </p>
          </div>
        </div>
        <button
          onClick={onToggle}
          className={`p-1 rounded-lg transition-all ${
            theme === 'dark' ? 'hover:bg-slate-800' : 'hover:bg-gray-100'
          }`}
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
      </div>

      {/* Stats */}
      <div className={`p-4 border-b ${
        theme === 'dark' ? 'border-slate-700/50' : 'border-gray-200'
      }`}>
        <div className={`flex items-center gap-2 text-sm mb-3 ${
          theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
        }`}>
          <Database className="w-4 h-4" />
          <span className="font-semibold">Statistics</span>
        </div>
        <div className="space-y-2">
          <div className={`backdrop-blur-xl border rounded-xl p-3 transition-all ${
            theme === 'dark'
              ? 'bg-slate-800/50 border-slate-700 hover:bg-slate-800'
              : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
          }`}>
            <div className="flex justify-between items-center">
              <span className={`text-sm font-medium ${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>Documents</span>
              <span className={`font-bold text-lg ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>{stats.num_documents}</span>
            </div>
          </div>
          <div className={`backdrop-blur-xl border rounded-xl p-3 transition-all ${
            theme === 'dark'
              ? 'bg-slate-800/50 border-slate-700 hover:bg-slate-800'
              : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
          }`}>
            <div className="flex justify-between items-center">
              <span className={`text-sm font-medium ${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>Chunks</span>
              <span className={`font-bold text-lg ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>{stats.num_chunks}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Upload Section */}
      <div className={`p-4 border-b ${
        theme === 'dark' ? 'border-slate-700/50' : 'border-gray-200'
      }`}>
        <DocumentUpload onUploadComplete={loadData} />
      </div>

      {/* Documents List */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className={`flex items-center gap-2 text-sm mb-3 ${
          theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
        }`}>
          <FileText className="w-4 h-4" />
          <span className="font-semibold">Documents</span>
        </div>
        
        {documents.length === 0 ? (
          <p className={`text-sm text-center py-8 ${
            theme === 'dark' ? 'text-slate-500' : 'text-slate-400'
          }`}>
            No documents yet.<br />
            Upload documents to get started.
          </p>
        ) : (
          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.doc_id}
                className={`p-3 backdrop-blur-xl border rounded-xl hover:shadow-lg transition-all group ${
                  theme === 'dark'
                    ? 'bg-slate-800/50 border-slate-700 hover:bg-slate-800'
                    : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                }`}
              >
                <div className="flex items-start gap-2">
                  <FileText className="w-4 h-4 mt-0.5 flex-shrink-0 text-primary-400" />
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${
                      theme === 'dark' ? 'text-white' : 'text-slate-900'
                    }`}>
                      {doc.filename}
                    </p>
                    <div className={`flex gap-3 mt-1 text-xs ${
                      theme === 'dark' ? 'text-slate-500' : 'text-slate-500'
                    }`}>
                      <span>{doc.file_type.toUpperCase()}</span>
                      <span>{(doc.file_size / 1024).toFixed(1)} KB</span>
                      <span>{doc.num_chunks} chunks</span>
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => handleSummarize(doc.doc_id)}
                      disabled={summarizing === doc.doc_id}
                      className={`opacity-0 group-hover:opacity-100 p-1.5 rounded-lg transition-all backdrop-blur-xl border ${
                        theme === 'dark'
                          ? 'hover:bg-purple-500/20 border-purple-500/20'
                          : 'hover:bg-purple-50 border-purple-200'
                      } disabled:opacity-50`}
                      title="Summarize document"
                    >
                      {summarizing === doc.doc_id ? (
                        <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                      ) : (
                        <FileSpreadsheet className="w-4 h-4 text-purple-400" />
                      )}
                    </button>
                    <button
                      onClick={() => handleDelete(doc.doc_id, doc.filename)}
                      className={`opacity-0 group-hover:opacity-100 p-1.5 rounded-lg transition-all backdrop-blur-xl border ${
                        theme === 'dark'
                          ? 'hover:bg-red-500/20 border-red-500/20'
                          : 'hover:bg-red-50 border-red-200'
                      }`}
                      title="Delete document"
                    >
                      <Trash2 className="w-4 h-4 text-red-400" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
