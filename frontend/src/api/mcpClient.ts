import axios from 'axios'

const api = axios.create({ baseURL: '/api/mcp-servers', headers: { 'Content-Type': 'application/json' } })

export type Transport = 'stdio' | 'sse' | 'http'
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export interface ServerConfig {
  id: string
  name: string
  transport: Transport
  enabled: boolean
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
  headers?: Record<string, string>
  created_at: string
  updated_at: string
}

export interface ServerStatus {
  server_id: string
  status: ConnectionStatus
  error_message?: string
  tool_count: number
  last_connected_at?: string
  session_meta: Record<string, any>
}

export interface ToolDefinition {
  server_id: string
  server_name: string
  tool_id: string
  name: string
  description: string
  input_schema: Record<string, any>
}

export interface ServerWithStatus {
  config: ServerConfig
  status: ServerStatus
  tools: ToolDefinition[]
}

export interface ServerCreateRequest {
  name: string
  transport: Transport
  enabled: boolean
  connect_now: boolean
  command?: string
  args?: string[]
  env?: Record<string, string>
  url?: string
  headers?: Record<string, string>
}

export interface TestResult {
  success: boolean
  tool_count: number
  tools: ToolDefinition[]
  latency_ms?: number
  error?: string
}

export interface ImportResult {
  created: number
  updated: number
  skipped: number
}

export interface PathSuggestion {
  label: string
  path: string
}

export interface ToolCallTrace {
  tool_name: string
  args: Record<string, any>
  result: string
}

export interface MCPChatMessage {
  role: 'user' | 'assistant'
  content: string
  tool_calls: ToolCallTrace[]
}

export interface MCPChatResponse {
  response: string
  conversation_id: string
  tool_calls: ToolCallTrace[]
  history: MCPChatMessage[]
}

export const mcpApi = {
  list: (): Promise<ServerWithStatus[]> =>
    api.get<ServerWithStatus[]>('').then(r => r.data),

  get: (id: string): Promise<ServerWithStatus> =>
    api.get<ServerWithStatus>(`/${id}`).then(r => r.data),

  create: (body: ServerCreateRequest): Promise<ServerWithStatus> =>
    api.post<ServerWithStatus>('', body).then(r => r.data),

  patch: (id: string, patch: Partial<ServerCreateRequest>): Promise<ServerWithStatus> =>
    api.patch<ServerWithStatus>(`/${id}`, patch).then(r => r.data),

  delete: (id: string): Promise<void> =>
    api.delete(`/${id}`).then(() => {}),

  connect: (id: string): Promise<ServerStatus> =>
    api.post<ServerStatus>(`/${id}/connect`).then(r => r.data),

  disconnect: (id: string): Promise<ServerStatus> =>
    api.post<ServerStatus>(`/${id}/disconnect`).then(r => r.data),

  tools: (id: string): Promise<ToolDefinition[]> =>
    api.get<ToolDefinition[]>(`/${id}/tools`).then(r => r.data),

  test: (id: string): Promise<TestResult> =>
    api.post<TestResult>(`/${id}/test`).then(r => r.data),

  import: (mcpServers: Record<string, any>, connect_now = false): Promise<ImportResult> =>
    api.post<ImportResult>('/import', { mcpServers, connect_now }).then(r => r.data),

  export: (): Promise<{ mcpServers: Record<string, any> }> =>
    api.get('/export').then(r => r.data),

  pathSuggestions: (): Promise<PathSuggestion[]> =>
    api.get<PathSuggestion[]>('/path-suggestions').then(r => r.data),

  chat: (message: string, conversationId: string, toolFilter?: string[]): Promise<MCPChatResponse> =>
    api.post<MCPChatResponse>('/chat', { message, conversation_id: conversationId, tool_filter: toolFilter ?? null }).then(r => r.data),

  getChatHistory: (conversationId: string): Promise<MCPChatMessage[]> =>
    api.get<MCPChatMessage[]>(`/chat/${conversationId}`).then(r => r.data),

  clearChatHistory: (conversationId: string): Promise<void> =>
    api.delete(`/chat/${conversationId}`).then(() => {}),

  login: (id: string): Promise<{ server: string; result: string }> =>
    api.post<{ server: string; result: string }>(`/${id}/login`).then(r => r.data),

  seedNews: (connectNow = true): Promise<ServerWithStatus> =>
    api.post<ServerWithStatus>(`/seed-news?connect_now=${connectNow}`).then(r => r.data),
}
