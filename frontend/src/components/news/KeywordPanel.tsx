import { useState, useEffect, useRef } from 'react';
import { Tag, ChevronDown, ChevronUp } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { newsApi, Keyword } from '../../api/newsApi';
import KeywordForm from './KeywordForm';
import KeywordCard from './KeywordCard';

interface Props {
  selectedKeywordId: string | null;
  onSelect: (kw: Keyword | null) => void;
}

const KW_POLL_MS = 10_000;

export default function KeywordPanel({ selectedKeywordId, onSelect }: Props) {
  const { theme } = useTheme();
  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(true);
  const [newArticlesMap, setNewArticlesMap] = useState<Record<string, number>>({});
  const prevCountsRef = useRef<Record<string, number>>({});
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = async (silent = false) => {
    try {
      const kws = await newsApi.getKeywords();
      setKeywords(kws);
      // Detect per-keyword count increases
      const newMap: Record<string, number> = {};
      kws.forEach(kw => {
        const prev = prevCountsRef.current[kw.id];
        if (prev !== undefined && kw.article_count > prev) {
          newMap[kw.id] = kw.article_count - prev;
        }
        prevCountsRef.current[kw.id] = kw.article_count;
      });
      if (Object.keys(newMap).length > 0) {
        setNewArticlesMap(prev => ({ ...prev, ...newMap }));
      }
    } catch {
      // silent — news service may be disabled
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    load();
    pollRef.current = setInterval(() => load(true), KW_POLL_MS);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleCreated = (kw: Keyword) => {
    setKeywords(prev => [kw, ...prev]);
    setShowForm(false);
    onSelect(kw);
  };

  const handleUpdated = (kw: Keyword) =>
    setKeywords(prev => prev.map(k => k.id === kw.id ? kw : k));

  const handleDeleted = (id: string) => {
    setKeywords(prev => prev.filter(k => k.id !== id));
    if (selectedKeywordId === id) onSelect(null);
  };

  const handleSelect = (id: string | null) => {
    if (id) setNewArticlesMap(prev => { const n = { ...prev }; delete n[id]; return n; });
    onSelect(id ? (keywords.find(k => k.id === id) ?? null) : null);
  };

  const muted = theme === 'dark' ? 'text-slate-400' : 'text-slate-500';
  const border = theme === 'dark' ? 'border-slate-700/50' : 'border-gray-200';

  return (
    <div className={`flex flex-col h-full border-r ${border}`}>
      {/* Header */}
      <div className={`p-4 border-b flex-shrink-0 ${border}`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Tag className={`w-4 h-4 ${muted}`} />
            <span className={`font-semibold text-sm ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
              Tracked Keywords
            </span>
          </div>
          <button
            onClick={() => setShowForm(v => !v)}
            className={`flex items-center gap-1 text-xs px-2 py-1 rounded-lg font-medium transition-colors ${
              theme === 'dark'
                ? 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30'
                : 'bg-blue-50 text-blue-600 hover:bg-blue-100'
            }`}
          >
            {showForm ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {showForm ? 'Hide' : '+ Add'}
          </button>
        </div>
        {showForm && <KeywordForm onCreated={handleCreated} />}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {loading ? (
          <p className={`text-xs text-center py-8 ${muted}`}>Loading…</p>
        ) : keywords.length === 0 ? (
          <p className={`text-xs text-center py-10 leading-relaxed ${muted}`}>
            No keywords yet.<br />
            Add your first keyword above<br />to start tracking news.
          </p>
        ) : (
          <>
            {/* "All" pill */}
            <div
              onClick={() => handleSelect(null)}
              className={`px-3 py-2 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
                selectedKeywordId === null
                  ? theme === 'dark'
                    ? 'bg-slate-700 text-white'
                    : 'bg-gray-200 text-slate-900'
                  : theme === 'dark'
                  ? `${muted} hover:bg-slate-800`
                  : `${muted} hover:bg-gray-100`
              }`}
            >
              All Keywords
              <span className={`ml-1.5 font-normal ${muted}`}>
                ({keywords.reduce((s, k) => s + k.article_count, 0)})
              </span>
            </div>

            {keywords.map(kw => (
              <KeywordCard
                key={kw.id}
                keyword={kw}
                selected={selectedKeywordId === kw.id}
                newArticles={newArticlesMap[kw.id] ?? 0}
                onUpdated={handleUpdated}
                onDeleted={handleDeleted}
                onSelect={handleSelect}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
