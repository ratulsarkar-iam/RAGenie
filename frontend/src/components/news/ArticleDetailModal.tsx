import { useEffect, useRef, useState } from 'react';
import { X, ExternalLink, RefreshCw, Loader2, CalendarDays, Clock } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { useToast } from '../../contexts/ToastContext';
import { newsApi, ArticleWithSummary } from '../../api/newsApi';

interface Props {
  article: ArticleWithSummary | null;
  onClose: () => void;
  onUpdated: (article: ArticleWithSummary) => void;
}

function parseUTC(iso: string): Date {
  const needsZ = iso && !iso.endsWith('Z') && !iso.includes('+');
  return new Date(needsZ ? iso + 'Z' : iso);
}

function formatDate(iso: string | null): string {
  if (!iso) return '';
  return parseUTC(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

type Tab = 'summary' | 'content';

export default function ArticleDetailModal({ article, onClose, onUpdated }: Props) {
  const { theme } = useTheme();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>('summary');
  const [regenerating, setRegenerating] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (article) {
      el.showModal();
      setTab('summary');
    } else {
      el.close();
    }
  }, [article]);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    const onCancel = (e: Event) => { e.preventDefault(); onClose(); };
    el.addEventListener('cancel', onCancel);
    return () => el.removeEventListener('cancel', onCancel);
  }, [onClose]);

  const handleRegenerate = async () => {
    if (!article) return;
    setRegenerating(true);
    try {
      const updated = await newsApi.resummarize(article.id);
      onUpdated(updated);
      toast('Summary updated', 'success');
    } catch {
      toast('Failed to regenerate summary', 'error');
    } finally {
      setRegenerating(false);
    }
  };

  const isDark = theme === 'dark';
  const muted = isDark ? 'text-slate-400' : 'text-slate-500';

  if (!article) return (
    <dialog ref={dialogRef} className="hidden" />
  );

  return (
    <dialog
      ref={dialogRef}
      aria-modal="true"
      aria-labelledby="detail-title"
      onClick={e => { if (e.target === dialogRef.current) onClose(); }}
      className={`rounded-2xl border shadow-2xl w-full max-w-3xl max-h-[90vh] p-0 overflow-hidden
        backdrop:bg-black/60
        ${isDark ? 'bg-slate-900 border-slate-700 text-white' : 'bg-white border-gray-200 text-slate-900'}`}
    >
      {/* Header */}
      <div className={`px-5 py-4 border-b flex items-start gap-3 ${isDark ? 'border-slate-700' : 'border-gray-200'}`}>
        <div className="flex-1 min-w-0">
          <h2 id="detail-title" className="font-semibold text-sm leading-snug">
            {article.title}
          </h2>
          <div className={`flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1.5 text-xs ${muted}`}>
            {article.source && (
              <span className={`px-1.5 py-0.5 rounded font-medium ${isDark ? 'bg-slate-700 text-slate-300' : 'bg-gray-100 text-slate-600'}`}>
                {article.source}
              </span>
            )}
            {article.published_at && (
              <span className="flex items-center gap-0.5">
                <CalendarDays className="w-3 h-3" />
                {formatDate(article.published_at)}
              </span>
            )}
            <span className="flex items-center gap-0.5">
              <Clock className="w-3 h-3" />
              {formatDate(article.fetched_at)}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className={`p-1.5 rounded-lg transition-colors ${isDark ? `hover:bg-slate-700 ${muted}` : `hover:bg-gray-100 ${muted}`}`}
            title="Read full article"
            aria-label="Read full article in new tab"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
          <button
            onClick={onClose}
            className={`p-1.5 rounded-lg transition-colors ${isDark ? `hover:bg-slate-700 ${muted}` : `hover:bg-gray-100 ${muted}`}`}
            aria-label="Close article detail"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Mobile tabs */}
      <div className={`flex md:hidden border-b ${isDark ? 'border-slate-700' : 'border-gray-200'}`}>
        {(['summary', 'content'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2.5 text-xs font-medium capitalize transition-colors ${
              tab === t
                ? isDark ? 'text-blue-400 border-b-2 border-blue-400' : 'text-blue-600 border-b-2 border-blue-600'
                : isDark ? `${muted} hover:text-slate-300` : `${muted} hover:text-slate-700`
            }`}
          >
            {t === 'summary' ? 'AI Summary' : 'Full Content'}
          </button>
        ))}
      </div>

      {/* Body — side by side on desktop, tabbed on mobile */}
      <div className="flex overflow-hidden" style={{ maxHeight: 'calc(90vh - 120px)' }}>
        {/* Summary panel */}
        <div className={`w-full md:w-1/2 overflow-y-auto p-5 flex flex-col gap-3
          ${tab !== 'summary' ? 'hidden md:flex' : 'flex'}
          ${isDark ? 'md:border-r border-slate-700' : 'md:border-r border-gray-200'}`}
        >
          <div className="flex items-center justify-between">
            <h3 className={`text-xs font-semibold uppercase tracking-wide ${muted}`}>AI Summary</h3>
            <button
              onClick={handleRegenerate}
              disabled={regenerating}
              className={`flex items-center gap-1 px-2 py-1 rounded-lg text-xs transition-colors disabled:opacity-50 ${
                isDark ? `hover:bg-slate-700 ${muted}` : `hover:bg-gray-100 ${muted}`
              }`}
              aria-label="Regenerate summary"
            >
              {regenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              Regenerate
            </button>
          </div>
          {article.summary ? (
            <p className={`text-sm leading-relaxed ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              {article.summary}
            </p>
          ) : (
            <div className="space-y-2">
              {[90, 75, 55, 80].map((w, i) => (
                <div key={i} className={`h-3 rounded animate-pulse ${isDark ? 'bg-slate-700' : 'bg-gray-200'}`}
                  style={{ width: `${w}%` }} />
              ))}
            </div>
          )}
        </div>

        {/* Content panel */}
        <div className={`w-full md:w-1/2 overflow-y-auto p-5 flex flex-col gap-3
          ${tab !== 'content' ? 'hidden md:flex' : 'flex'}`}
        >
          <h3 className={`text-xs font-semibold uppercase tracking-wide ${muted}`}>Full Content</h3>
          {article.content ? (
            <p className={`text-sm leading-relaxed whitespace-pre-wrap ${isDark ? 'text-slate-300' : 'text-slate-700'}`}>
              {article.content}
            </p>
          ) : (
            <p className={`text-sm italic ${muted}`}>No content available.</p>
          )}
        </div>
      </div>
    </dialog>
  );
}
