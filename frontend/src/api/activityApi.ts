import axios from 'axios'
import { authHeader } from './authToken'

// Backend mounts activity routes at "/api/activity/*" — use the absolute backend
// URL like other "/api/..."-prefixed clients (newsApi.ts, analytics.ts, assistant.ts).
const api = axios.create({ baseURL: 'http://localhost:8000/api/activity', headers: { 'Content-Type': 'application/json' } })

export interface ActivityEvent {
  id: string
  user_id: string
  event_type: string
  description: string
  metadata: Record<string, any> | null
  created_at: string
}

export interface ActivityListParams {
  event_type?: string
  user_id?: string
  page?: number
  limit?: number
}

function buildQuery(params: ActivityListParams): string {
  const q = new URLSearchParams()
  if (params.event_type) q.set('event_type', params.event_type)
  if (params.user_id) q.set('user_id', params.user_id)
  if (params.page) q.set('page', String(params.page))
  if (params.limit) q.set('limit', String(params.limit))
  return q.toString()
}

export const activityApi = {
  listMine: (params: ActivityListParams = {}): Promise<ActivityEvent[]> =>
    api.get<ActivityEvent[]>(`?${buildQuery(params)}`, { headers: authHeader() }).then(r => r.data),

  listAll: (params: ActivityListParams = {}): Promise<ActivityEvent[]> =>
    api.get<ActivityEvent[]>(`/admin?${buildQuery(params)}`, { headers: authHeader() }).then(r => r.data),
}

export const ACTIVITY_EVENT_TYPES = [
  'login',
  'logout',
  'chat_message',
  'document_uploaded',
  'document_deleted',
  'keyword_created',
  'keyword_updated',
  'keyword_deleted',
  'news_search',
  'news_fetch_now',
  'mcp_server_created',
  'mcp_server_updated',
  'mcp_server_deleted',
  'mcp_server_connected',
  'mcp_server_disconnected',
  'mcp_tool_call',
  'memory_search',
] as const
