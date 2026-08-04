import { authHeader } from './authToken'

const BASE = 'http://localhost:8000/api'

function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  return fetch(url, {
    ...options,
    headers: { ...(options.headers || {}), ...authHeader() },
  })
}

// ── Memory ────────────────────────────────────────────────────────────────────

export interface Memory {
  id: string
  content: string
  type: string
  timestamp: string
  metadata?: Record<string, any>
}

export async function storeMemory(
  content: string,
  type = 'context',
  metadata: Record<string, any> = {}
): Promise<{ memory_id: string; status: string }> {
  const res = await authFetch(`${BASE}/memory/store`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, type, metadata }),
  })
  if (!res.ok) throw new Error(`Store memory failed: ${res.statusText}`)
  return res.json()
}

export async function searchMemories(
  q: string,
  limit = 10
): Promise<{ memories: Memory[]; count: number }> {
  const res = await authFetch(`${BASE}/memory/search?q=${encodeURIComponent(q)}&limit=${limit}`)
  if (!res.ok) throw new Error(`Search memories failed: ${res.statusText}`)
  return res.json()
}

export async function getMemoryProfile(): Promise<Record<string, any>> {
  const res = await authFetch(`${BASE}/memory/profile`)
  if (!res.ok) throw new Error(`Get profile failed: ${res.statusText}`)
  return res.json()
}

// ── Tasks ─────────────────────────────────────────────────────────────────────

export interface TaskResult {
  success: boolean
  summary: string
  details: Record<string, any>
  task_type?: string
}

export async function executeTask(request: string): Promise<TaskResult> {
  const res = await authFetch(`${BASE}/tasks/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request }),
  })
  if (!res.ok) throw new Error(`Task execution failed: ${res.statusText}`)
  return res.json()
}

// ── Feedback ──────────────────────────────────────────────────────────────────

export async function submitFeedback(
  type: string,
  rating: 'thumbs_up' | 'thumbs_down',
  messageId: string,
  comment = ''
): Promise<{ status: string; feedback_id: string }> {
  const res = await authFetch(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type, rating, message_id: messageId, comment }),
  })
  if (!res.ok) throw new Error(`Submit feedback failed: ${res.statusText}`)
  return res.json()
}

// ── Learning ──────────────────────────────────────────────────────────────────

export interface LearningSummary {
  total_feedback: number
  positive_rate: number
  topics_covered: string[]
  mastery_overview: Record<string, number>
  recent_activity: any[]
}

export async function getLearningSummary(): Promise<LearningSummary> {
  const res = await authFetch(`${BASE}/learning/summary`)
  if (!res.ok) throw new Error(`Get learning summary failed: ${res.statusText}`)
  return res.json()
}

// ── Proactive ─────────────────────────────────────────────────────────────────

export async function triggerBriefing(): Promise<{ status: string }> {
  const res = await authFetch(`${BASE}/proactive/briefing`, { method: 'POST' })
  if (!res.ok) throw new Error(`Trigger briefing failed: ${res.statusText}`)
  return res.json()
}

export async function getDueReviews(): Promise<{ due_reviews: any[] }> {
  const res = await authFetch(`${BASE}/proactive/due-reviews`)
  if (!res.ok) throw new Error(`Get due reviews failed: ${res.statusText}`)
  return res.json()
}
