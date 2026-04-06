import { useState, useRef } from 'react'
import { Upload, X, FileText, Loader2, CheckCircle, AlertCircle } from 'lucide-react'
import axios from 'axios'
import { useTheme } from '../contexts/ThemeContext'

interface DocumentUploadProps {
  onUploadComplete: () => void
}

export default function DocumentUpload({ onUploadComplete }: DocumentUploadProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [statusMessage, setStatusMessage] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { theme } = useTheme()

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setUploading(true)
    setUploadStatus('idle')
    setStatusMessage('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      setUploadStatus('success')
      setStatusMessage(`Successfully uploaded: ${response.data.filename} (${response.data.num_chunks} chunks)`)
      
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }

      // Notify parent to refresh document list
      setTimeout(() => {
        onUploadComplete()
        setIsOpen(false)
        setUploadStatus('idle')
        setStatusMessage('')
      }, 2000)

    } catch (error: any) {
      setUploadStatus('error')
      setStatusMessage(error.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className={`w-full p-3 backdrop-blur-xl border rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg ${
          theme === 'dark'
            ? 'bg-blue-600 border-blue-500 hover:bg-blue-500 text-white'
            : 'bg-blue-500 border-blue-400 hover:bg-blue-600 text-white'
        }`}
      >
        <Upload className="w-5 h-5" />
        <span className="font-medium">Upload Document</span>
      </button>
    )
  }

  return (
    <div className={`backdrop-blur-xl border rounded-xl p-4 space-y-4 shadow-lg ${
      theme === 'dark'
        ? 'bg-slate-800/50 border-slate-700'
        : 'bg-white border-gray-200'
    }`}>
      <div className="flex items-center justify-between">
        <h3 className={`font-semibold ${
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        }`}>Upload Document</h3>
        <button
          onClick={() => setIsOpen(false)}
          className={`p-1 rounded-lg transition-all ${
            theme === 'dark' ? 'hover:bg-slate-700' : 'hover:bg-gray-100'
          }`}
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="space-y-3">
        <div
          className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all backdrop-blur-xl ${
            theme === 'dark'
              ? 'border-slate-600 hover:border-slate-500 hover:bg-slate-700/50'
              : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
          }`}
          onClick={() => fileInputRef.current?.click()}
        >
          <FileText className={`w-12 h-12 mx-auto mb-3 ${
            theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
          }`} />
          <p className={`text-sm mb-1 font-medium ${
            theme === 'dark' ? 'text-slate-300' : 'text-slate-700'
          }`}>
            Click to select a file
          </p>
          <p className={`text-xs ${
            theme === 'dark' ? 'text-slate-500' : 'text-slate-500'
          }`}>
            Supported: PDF, TXT, Markdown
          </p>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md,.markdown"
          onChange={handleFileSelect}
          className="hidden"
        />

        {uploading && (
          <div className={`flex items-center gap-2 text-sm backdrop-blur-xl border rounded-lg p-3 ${
            theme === 'dark'
              ? 'text-slate-300 bg-slate-700/50 border-slate-600'
              : 'text-slate-700 bg-gray-50 border-gray-200'
          }`}>
            <Loader2 className="w-4 h-4 animate-spin" />
            <span>Uploading and processing...</span>
          </div>
        )}

        {uploadStatus === 'success' && (
          <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 backdrop-blur-xl border border-green-200 rounded-lg p-3">
            <CheckCircle className="w-4 h-4" />
            <span>{statusMessage}</span>
          </div>
        )}

        {uploadStatus === 'error' && (
          <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 backdrop-blur-xl border border-red-200 rounded-lg p-3">
            <AlertCircle className="w-4 h-4" />
            <span>{statusMessage}</span>
          </div>
        )}
      </div>
    </div>
  )
}
