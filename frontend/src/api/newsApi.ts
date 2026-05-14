const API_BASE_URL = 'http://localhost:8000';

export interface Keyword {
  id: string;
  term: string;
  enabled: boolean;
  fetch_interval_minutes: number;
  max_articles_per_fetch: number;
  created_at: string;
  last_fetched_at: string | null;
  article_count: number;
  last_error: string | null;
}

export interface KeywordCreate {
  term: string;
  fetch_interval_minutes?: number;
  max_articles_per_fetch?: number;
}

export interface ArticleWithSummary {
  id: string;
  keyword_id: string;
  title: string;
  content: string;
  url: string;
  source: string;
  published_at: string | null;
  fetched_at: string;
  is_summarised: boolean;
  rag_doc_id: string | null;
  summary: string | null;
  summary_model: string | null;
}

export interface TranslationLanguage {
  code: string;
  name: string;
  native: string;
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const e = new Error(err.detail || 'Request failed') as any;
    e.status = res.status;
    throw e;
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json();
}

export const newsApi = {
  getStatus: () =>
    request<{ enabled: boolean }>('/api/news/status'),

  getKeywords: () =>
    request<Keyword[]>('/api/keywords'),

  createKeyword: (data: KeywordCreate) =>
    request<Keyword>('/api/keywords', { method: 'POST', body: JSON.stringify(data) }),

  suggestKeyword: (description: string) =>
    request<{ term: string; explanation: string }>('/api/keywords/suggest', {
      method: 'POST',
      body: JSON.stringify({ description }),
    }),

  updateKeyword: (
    id: string,
    data: Partial<Pick<Keyword, 'term' | 'enabled' | 'fetch_interval_minutes' | 'max_articles_per_fetch'>>,
  ) =>
    request<Keyword>(`/api/keywords/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteKeyword: (id: string) =>
    request<void>(`/api/keywords/${id}`, { method: 'DELETE' }),

  fetchNow: (id: string) =>
    request<void>(`/api/keywords/${id}/fetch-now`, { method: 'POST' }),

  getArticles: (params: { keyword_id?: string; page?: number; limit?: number }) => {
    const q = new URLSearchParams();
    if (params.keyword_id) q.set('keyword_id', params.keyword_id);
    if (params.page)       q.set('page',       String(params.page));
    if (params.limit)      q.set('limit',      String(params.limit));
    return request<ArticleWithSummary[]>(`/api/news?${q}`);
  },

  resummarize: (articleId: string) =>
    request<ArticleWithSummary>(`/api/news/${articleId}/summarize`, { method: 'POST' }),

  deleteArticle: (articleId: string) =>
    request<void>(`/api/news/${articleId}`, { method: 'DELETE' }),

  getTranslationLanguages: () =>
    request<{ languages: TranslationLanguage[] }>('/api/news/translation-languages'),

  translateSummary: (articleId: string, languageCode: string) =>
    request<{ translated_summary: string; language_code: string }>(`/api/news/${articleId}/translate`, {
      method: 'POST',
      body: JSON.stringify({ language_code: languageCode }),
    }),
};
