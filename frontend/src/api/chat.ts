import axios from 'axios'

const API_BASE_URL = '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface ChatRequest {
  message: string
  conversation_id: string
  use_agent?: boolean
}

export interface ChatResponse {
  response: string
  conversation_id: string
}

export interface DocumentInfo {
  doc_id: string
  filename: string
  file_type: string
  file_size: number
  num_chunks: number
}

export interface HealthResponse {
  status: string
  num_documents: number
  num_chunks: number
}

export const sendMessage = async (
  message: string,
  conversationId: string = 'default',
  useAgent: boolean = false
): Promise<ChatResponse> => {
  const response = await api.post<ChatResponse>('/chat', {
    message,
    conversation_id: conversationId,
    use_agent: useAgent,
  })
  return response.data
}

export const getHistory = async (conversationId: string): Promise<any> => {
  const response = await api.get(`/history/${conversationId}`)
  return response.data
}

export const clearHistory = async (conversationId: string): Promise<void> => {
  await api.delete(`/history/${conversationId}`)
}

export const getDocuments = async (): Promise<DocumentInfo[]> => {
  const response = await api.get<DocumentInfo[]>('/documents')
  return response.data
}

export const getHealth = async (): Promise<HealthResponse> => {
  const response = await api.get<HealthResponse>('/health')
  return response.data
}

export const deleteDocument = async (docId: string): Promise<void> => {
  await api.delete(`/documents/${docId}`)
}

export const uploadDocument = async (file: File): Promise<any> => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export const summarizeDocument = async (docId: string): Promise<any> => {
  const response = await api.get(`/documents/${docId}/summarize`)
  return response.data
}

export interface ChatUploadResponse {
  status: string
  doc_id: string
  filename: string
  file_type: string
  file_size: number
  num_chunks: number
  preview: string
}

export const chatUploadFile = async (file: File): Promise<ChatUploadResponse> => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post<ChatUploadResponse>('/chat-upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 120000, // 2 min timeout for large files
  })
  return response.data
}
