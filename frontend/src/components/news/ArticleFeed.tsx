import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Newspaper, RefreshCw, Loader2, Search, X, SlidersHorizontal, BellDot, Menu } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { newsApi, ArticleWithSummary, Keyword } from '../../api/newsApi';
import ArticleCard from './ArticleCard';

interface Props {
  selectedKeyword: Keyword | null;
  onNewArticles?: (keywordId: string | null, count: number) => void;
  onOpenDetail?: (article: ArticleWithSummary) => void;
  onMenuToggle?: () => void;
}

const PAGE_SIZE = 20;
const REFRESH_MS = 5 * 60 * 1000;
const PENDING_POLL_MS = 15_000;
const BG_CHECK_MS = 60_000;

type TimeFilter   = 'all' | 'today' | '3d' | '7d';
type StatusFilter = 'all' | 'summarised' | 'pending';
type SortBy       = 'newest-added' | 'newest-published' | 'most-relevant';

const SORT_OPTS: { label: string; value: SortBy }[] = [
  { label: 'Newest added',    value: 'newest-added'     },
  { label: 'Newest published',value: 'newest-published'  },
  { label: 'Most relevant',   value: 'most-relevant'    },
];

function utcMs(iso: string | null): number {
  if (!iso) return 0;
  const s = iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z';
  return new Date(s).getTime();
}

function relevanceScore(article: ArticleWithSummary, term: string): number {
  if (!term) return 0;
  const tokens = term.toLowerCase().split(/\s+/).filter(Boolean);
  const title   = article.title.toLowerCase();
  const summary = (article.summary || '').toLowerCase();
  return tokens.reduce((sum, t) => {
    const re = new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
    return sum + (title.match(re)?.length ?? 0) * 3 + (summary.match(re)?.length ?? 0);
  }, 0);
}

const TIME_OPTS: { label: string; value: TimeFilter }[] = [
  { label: 'All time',   value: 'all'   },
  { label: 'Today',      value: 'today' },
  { label: 'Last 3 days',value: '3d'    },
  { label: 'Last week',  value: '7d'    },
];

const STATUS_OPTS: { label: string; value: StatusFilter }[] = [
  { label: 'All',       value: 'all'        },
  { label: 'Summarised',value: 'summarised' },
  { label: 'Pending',   value: 'pending'    },
];

export default function ArticleFeed({ selectedKeyword, onNewArticles, onOpenDetail, onMenuToggle }: Props) {
  const { theme } = useTheme();
  const [articles, setArticles] = useState<ArticleWithSummary[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newCount, setNewCount] = useState(0);
  const knownIdsRef = useRef<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bgCheckRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Filter & sort state ────────────────────────────────────────
  const [search, setSearch]             = useState('');
  const [timeFilter, setTimeFilter]     = useState<TimeFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [sortBy, setSortBy]             = useState<SortBy>('newest-added');
  const [showFilters, setShowFilters]   = useState(false);

  const load = useCallback(async (p: number, replace: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const data = await newsApi.getArticles({
        keyword_id: selectedKeyword?.id ?? undefined,
        page: p,
        limit: PAGE_SIZE,
      });
      if (replace) {
        knownIdsRef.current = new Set(data.map(a => a.id));
        setNewCount(0);
      } else {
        data.forEach(a => knownIdsRef.current.add(a.id));
      }
      setArticles(prev => replace ? data : [...prev, ...data]);
      setHasMore(data.length === PAGE_SIZE);
    } catch {
      setError('Failed to load articles.');
    } finally {
      setLoading(false);
    }
  }, [selectedKeyword?.id]);

  const bgCheck = useCallback(async () => {
    try {
      const data = await newsApi.getArticles({
        keyword_id: selectedKeyword?.id ?? undefined,
        page: 1,
        limit: PAGE_SIZE,
      });
      const fresh = data.filter(a => !knownIdsRef.current.has(a.id));
      if (fresh.length > 0) {
        setNewCount(fresh.length);
        onNewArticles?.(selectedKeyword?.id ?? null, fresh.length);
      }
    } catch { /* silent */ }
  }, [selectedKeyword?.id, onNewArticles]);

  const loadAndScrollTop = useCallback(() => {
    load(1, true);
    scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, [load]);

  useEffect(() => {
    setPage(1);
    setNewCount(0);
    knownIdsRef.current = new Set();
    load(1, true);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => load(1, true), REFRESH_MS);
    if (bgCheckRef.current) clearInterval(bgCheckRef.current);
    bgCheckRef.current = setInterval(bgCheck, BG_CHECK_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (bgCheckRef.current) clearInterval(bgCheckRef.current);
    };
  }, [selectedKeyword?.id, load, bgCheck]);

  // Fast-poll (15s) while any visible article is still awaiting its summary
  useEffect(() => {
    if (pendingTimerRef.current) clearTimeout(pendingTimerRef.current);
    const hasPending = articles.some(a => a.summary === null);
    if (!hasPending) return;
    pendingTimerRef.current = setTimeout(() => load(1, true), PENDING_POLL_MS);
    return () => { if (pendingTimerRef.current) clearTimeout(pendingTimerRef.current); };
  }, [articles, load]);

  const handleLoadMore = () => {
    const next = page + 1;
    setPage(next);
    load(next, false);
  };

  const handleDeleted = (id: string) =>
    setArticles(prev => prev.filter(a => a.id !== id));

  const handleUpdated = (updated: ArticleWithSummary) =>
    setArticles(prev => prev.map(a => a.id === updated.id ? updated : a));

  // ── Derived: filtered + sorted view ───────────────────────────
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return articles.filter(a => {
      if (q && !a.title.toLowerCase().includes(q)) return false;
      if (timeFilter !== 'all') {
        const days = timeFilter === 'today' ? 1 : timeFilter === '3d' ? 3 : 7;
        const cutoff = Date.now() - days * 86_400_000;
        if (utcMs(a.fetched_at) < cutoff) return false;
      }
      if (statusFilter === 'summarised' && !a.summary) return false;
      if (statusFilter === 'pending'    &&  a.summary) return false;
      return true;
    });
  }, [articles, search, timeFilter, statusFilter]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    if (sortBy === 'newest-added') {
      return arr.sort((a, b) => utcMs(b.fetched_at) - utcMs(a.fetched_at));
    }
    if (sortBy === 'newest-published') {
      return arr.sort((a, b) => {
        const diff = utcMs(b.published_at) - utcMs(a.published_at);
        return diff !== 0 ? diff : utcMs(b.fetched_at) - utcMs(a.fetched_at);
      });
    }
    // most-relevant: score by keyword term token overlap in title + summary
    const term = selectedKeyword?.term ?? '';
    return arr.sort((a, b) => {
      const diff = relevanceScore(b, term) - relevanceScore(a, term);
      return diff !== 0 ? diff : utcMs(b.fetched_at) - utcMs(a.fetched_at);
    });
  }, [filtered, sortBy, selectedKeyword?.term]);

  const isFiltered = search || timeFilter !== 'all' || statusFilter !== 'all';

  const muted = theme === 'dark' ? 'text-slate-400' : 'text-slate-500';
  const border = theme === 'dark' ? 'border-slate-700/50' : 'border-gray-200';

  const pillBase = 'px-2.5 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer';
  const pillActive = theme === 'dark' ? 'bg-blue-600 text-white' : 'bg-blue-500 text-white';
  const pillIdle   = theme === 'dark' ? `${muted} hover:bg-slate-700` : `${muted} hover:bg-gray-100`;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className={`px-4 pt-4 pb-3 border-b flex-shrink-0 space-y-3 ${border}`}>
        {/* Title row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {onMenuToggle && (
              <button
                onClick={onMenuToggle}
                className={`sm:hidden p-1 rounded-lg transition-colors ${theme === 'dark' ? `hover:bg-slate-700 ${muted}` : `hover:bg-gray-100 ${muted}`}`}
                aria-label="Toggle keyword panel"
              >
                <Menu className="w-4 h-4" />
              </button>
            )}
            <Newspaper className={`w-4 h-4 ${muted}`} />
            <span className={`font-semibold text-sm ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
              Articles
            </span>
            {articles.length > 0 && (
              <span className={`text-xs ${muted}`}>
                {isFiltered
                  ? `${sorted.length} / ${articles.length}${hasMore ? '+' : ''}`
                  : `${articles.length}${hasMore ? '+' : ''}`}
              </span>
            )}
            {articles.some(a => a.summary === null) && (
              <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                theme === 'dark' ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-100 text-amber-600'
              }`}>
                <Loader2 className="w-3 h-3 animate-spin" />
                Summarising…
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowFilters(v => !v)}
              className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium transition-colors ${
                showFilters || isFiltered
                  ? theme === 'dark' ? 'bg-blue-600/20 text-blue-400' : 'bg-blue-50 text-blue-600'
                  : theme === 'dark' ? `hover:bg-slate-700 ${muted}` : `hover:bg-gray-100 ${muted}`
              }`}
              title="Filters"
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              Filter
              {isFiltered && (
                <span className="ml-0.5 w-1.5 h-1.5 rounded-full bg-blue-500" />
              )}
            </button>
            <button
              onClick={() => load(1, true)}
              disabled={loading}
              className={`p-1.5 rounded-lg transition-colors disabled:opacity-50 ${
                theme === 'dark' ? `hover:bg-slate-700 ${muted}` : `hover:bg-gray-100 ${muted}`
              }`}
              title="Refresh"
            >
              {loading
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <RefreshCw className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* ── Sort row (always visible) ─────────────────────────────── */}
        <div className="flex items-center gap-1.5">
          <span className={`text-xs ${muted} flex-shrink-0`}>Sort:</span>
          {SORT_OPTS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setSortBy(opt.value)}
              className={`${pillBase} ${sortBy === opt.value ? pillActive : pillIdle}`}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* ── Filter panel ─────────────────────────────────────────── */}
        {showFilters && (
          <div className="space-y-2">
            {/* Search */}
            <div className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border ${
              theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'
            }`}>
              <Search className={`w-3.5 h-3.5 flex-shrink-0 ${muted}`} />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search articles…"
                className={`flex-1 text-xs bg-transparent outline-none ${
                  theme === 'dark' ? 'text-white placeholder-slate-500' : 'text-slate-900 placeholder-slate-400'
                }`}
              />
              {search && (
                <button onClick={() => setSearch('')}>
                  <X className={`w-3.5 h-3.5 ${muted} hover:text-red-400`} />
                </button>
              )}
            </div>

            {/* Time pills */}
            <div className="flex flex-wrap gap-1">
              {TIME_OPTS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setTimeFilter(opt.value)}
                  className={`${pillBase} ${timeFilter === opt.value ? pillActive : pillIdle}`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {/* Status pills */}
            <div className="flex flex-wrap gap-1 items-center">
              <span className={`text-xs ${muted} mr-1`}>Summary:</span>
              {STATUS_OPTS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setStatusFilter(opt.value)}
                  className={`${pillBase} ${statusFilter === opt.value ? pillActive : pillIdle}`}
                >
                  {opt.label}
                </button>
              ))}
              {isFiltered && (
                <button
                  onClick={() => { setSearch(''); setTimeFilter('all'); setStatusFilter('all'); }}
                  className={`ml-auto text-xs flex items-center gap-0.5 ${
                    theme === 'dark' ? 'text-red-400 hover:text-red-300' : 'text-red-500 hover:text-red-600'
                  }`}
                >
                  <X className="w-3 h-3" /> Clear all
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── New articles banner ───────────────────────────────────── */}
      {newCount > 0 && (
        <div className={`flex items-center justify-between px-4 py-2 border-b flex-shrink-0 ${
          theme === 'dark'
            ? 'bg-blue-900/30 border-blue-700/50'
            : 'bg-blue-50 border-blue-200'
        }`}>
          <span className={`flex items-center gap-1.5 text-xs font-medium ${
            theme === 'dark' ? 'text-blue-300' : 'text-blue-700'
          }`}>
            <BellDot className="w-3.5 h-3.5" />
            {newCount} new article{newCount > 1 ? 's' : ''} available
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={loadAndScrollTop}
              className={`text-xs font-semibold px-2.5 py-1 rounded-lg transition-colors ${
                theme === 'dark'
                  ? 'bg-blue-600 hover:bg-blue-500 text-white'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              Load
            </button>
            <button
              onClick={() => setNewCount(0)}
              className={`text-xs ${theme === 'dark' ? 'text-slate-400 hover:text-slate-300' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* ── Article list ───────────────────────────────────────────── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {error && (
          <p className={`text-sm text-center py-6 ${theme === 'dark' ? 'text-red-400' : 'text-red-500'}`}>
            {error}{' '}
            <button onClick={() => load(1, true)} className="underline font-medium">Retry</button>
          </p>
        )}

        {!loading && !error && articles.length === 0 && (
          <p className={`text-xs text-center py-16 leading-relaxed ${muted}`}>
            No articles yet —<br />
            click <strong>Fetch Now</strong> on a keyword to start.
          </p>
        )}

        {!error && articles.length > 0 && sorted.length === 0 && (
          <p className={`text-xs text-center py-12 leading-relaxed ${muted}`}>
            No articles match the current filters.
            <br />
            <button
              onClick={() => { setSearch(''); setTimeFilter('all'); setStatusFilter('all'); }}
              className="mt-1 underline"
            >
              Clear filters
            </button>
          </p>
        )}

        {sorted.map(a => (
          <ArticleCard
            key={a.id}
            article={a}
            onDeleted={handleDeleted}
            onUpdated={handleUpdated}
            onOpenDetail={onOpenDetail}
          />
        ))}

        {hasMore && (
          <button
            onClick={handleLoadMore}
            disabled={loading}
            className={`w-full py-2 text-xs font-medium rounded-lg border transition-colors disabled:opacity-50 ${
              theme === 'dark'
                ? `border-slate-700 ${muted} hover:bg-slate-800`
                : `border-gray-200 ${muted} hover:bg-gray-50`
            }`}
          >
            {loading
              ? <Loader2 className="w-4 h-4 animate-spin mx-auto" />
              : 'Load more'}
          </button>
        )}
      </div>
    </div>
  );
}
