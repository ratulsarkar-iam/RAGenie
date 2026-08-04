import { useState } from 'react';
import { ExternalLink, ChevronDown, ChevronUp, RefreshCw, Loader2, Trash2, Clock, CalendarDays, Languages, Expand } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { useTranslation } from '../../contexts/TranslationContext';
import { useToast } from '../../contexts/ToastContext';
import { newsApi, ArticleWithSummary } from '../../api/newsApi';
import ConfirmDialog from '../shared/ConfirmDialog';

const RETENTION_DAYS = 3;

function retentionBadge(fetchedAt: string): { label: string; cls: string } | null {
  const expiresAt = parseUTC(fetchedAt).getTime() + RETENTION_DAYS * 86_400_000;
  const remainingH = (expiresAt - Date.now()) / 3_600_000;
  if (remainingH <= 0 || remainingH > 12) return null;
  const label = `Expires in ${Math.ceil(remainingH)}h`;
  if (remainingH <= 6)
    return { label, cls: 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-900/30 border border-red-200 dark:border-red-800' };
  return { label, cls: 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800' };
}

interface Props {
  article: ArticleWithSummary;
  onDeleted: (id: string) => void;
  onUpdated: (article: ArticleWithSummary) => void;
  onOpenDetail?: (article: ArticleWithSummary) => void;
}

/** SQLite stores UTC datetimes without a timezone suffix.
 *  Appending 'Z' forces the browser to parse as UTC, then auto-converts
 *  to the user's local timezone for display. */
function parseUTC(iso: string): Date {
  const needsZ = iso && !iso.endsWith('Z') && !iso.includes('+');
  return new Date(needsZ ? iso + 'Z' : iso);
}

function relativeTime(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - parseUTC(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'Just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function formatAdded(iso: string): string {
  const d = parseUTC(iso);
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function formatPublished(iso: string | null): string {
  if (!iso) return '';
  const d = parseUTC(iso);
  const diffH = (Date.now() - d.getTime()) / 3600000;
  if (diffH < 24) return relativeTime(iso);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: diffH > 8760 ? 'numeric' : undefined });
}

export default function ArticleCard({ article, onDeleted, onUpdated, onOpenDetail }: Props) {
  const { theme } = useTheme();
  const { languages } = useTranslation();
  const toast = useToast();
  const [summaryOpen, setSummaryOpen] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [translatedSummary, setTranslatedSummary] = useState<string | null>(null);
  const [translatedLang, setTranslatedLang] = useState<string | null>(null);
  const [showLangMenu, setShowLangMenu] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleRegenerate = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setRegenerating(true);
    setTranslatedSummary(null);
    setTranslatedLang(null);
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

  const handleTranslate = async (langCode: string) => {
    setShowLangMenu(false);
    setTranslating(true);
    try {
      const res = await newsApi.translateSummary(article.id, langCode);
      setTranslatedSummary(res.translated_summary);
      setTranslatedLang(langCode);
    } catch {
      // silently fail
    } finally {
      setTranslating(false);
    }
  };

  const clearTranslation = () => {
    setTranslatedSummary(null);
    setTranslatedLang(null);
  };

  const handleDelete = async () => {
    try {
      await newsApi.deleteArticle(article.id);
      onDeleted(article.id);
      toast('Article removed', 'info');
    } catch {
      toast('Failed to delete article', 'error');
    }
  };

  const muted = theme === 'dark' ? 'text-slate-400' : 'text-slate-500';

  const retention = retentionBadge(article.fetched_at);

  return (
    <>
    <ConfirmDialog
      open={confirmDelete}
      title="Remove article"
      message={`Remove "${article.title.slice(0, 60)}…"? This cannot be undone.`}
      confirmLabel="Remove"
      danger
      onConfirm={() => { setConfirmDelete(false); handleDelete(); }}
      onCancel={() => setConfirmDelete(false)}
    />
    <div className={`rounded-xl border p-4 transition-all ${
      theme === 'dark'
        ? 'bg-slate-800/60 border-slate-700 hover:bg-slate-800'
        : 'bg-white border-gray-200 hover:bg-gray-50'
    }`}>
      {/* Retention badge */}
      {retention && (
        <div role="status" className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium mb-2 ${retention.cls}`}>
          {retention.label}
        </div>
      )}
      {/* Title row */}
      <div className="flex items-start gap-2">
        {article.image_url && (
          <img
            src={article.image_url}
            alt=""
            className="w-16 h-14 object-cover rounded-lg flex-shrink-0 mt-0.5"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
          />
        )}
        <div className="flex-1 min-w-0">
          <button
            onClick={() => onOpenDetail?.(article)}
            className={`text-left text-sm font-semibold leading-snug hover:underline ${
              theme === 'dark' ? 'text-white' : 'text-slate-900'
            } ${onOpenDetail ? 'cursor-pointer' : 'cursor-default'}`}
            aria-label={`Open detail for: ${article.title}`}
          >
            {article.title}
          </button>
          <div className={`flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-1 text-xs ${muted}`}>
            {article.source && (
              <span className={`px-1.5 py-0.5 rounded font-medium ${
                theme === 'dark' ? 'bg-slate-700 text-slate-300' : 'bg-gray-100 text-slate-600'
              }`}>
                {article.source}
              </span>
            )}
            {article.published_at && (
              <span className="flex items-center gap-0.5">
                <CalendarDays className="w-3 h-3" />
                {formatPublished(article.published_at)}
              </span>
            )}
            <span className={`flex items-center gap-0.5 font-medium ${
              theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
            }`}>
              <Clock className="w-3 h-3" />
              {formatAdded(article.fetched_at)}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-0.5 flex-shrink-0">
          {onOpenDetail && (
            <button
              onClick={() => onOpenDetail(article)}
              className={`p-1.5 rounded-lg transition-colors ${theme === 'dark' ? `hover:bg-slate-700 ${muted}` : `hover:bg-gray-100 ${muted}`}`}
              title="View detail"
              aria-label="View article detail"
            >
              <Expand className="w-3.5 h-3.5" />
            </button>
          )}
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className={`p-1.5 rounded-lg transition-colors ${
              theme === 'dark' ? `hover:bg-slate-700 ${muted}` : `hover:bg-gray-100 ${muted}`
            }`}
            title="Read full article"
            aria-label="Read full article in new tab"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
          <button
            onClick={() => setConfirmDelete(true)}
            className={`p-1.5 rounded-lg transition-colors ${
              theme === 'dark' ? 'hover:bg-red-900/30 text-red-400' : 'hover:bg-red-50 text-red-500'
            }`}
            title="Delete article"
            aria-label="Delete article"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* AI Summary section */}
      <div className="mt-3">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setSummaryOpen(v => !v)}
            aria-expanded={summaryOpen}
            aria-controls={`summary-${article.id}`}
            className={`flex items-center gap-1 text-xs font-medium transition-colors ${
              theme === 'dark' ? 'text-blue-400 hover:text-blue-300' : 'text-blue-600 hover:text-blue-700'
            }`}
          >
            {summaryOpen
              ? <ChevronUp className="w-3.5 h-3.5" />
              : <ChevronDown className="w-3.5 h-3.5" />}
            AI Summary
          </button>
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className={`p-0.5 rounded transition-colors disabled:opacity-50 ${
              theme === 'dark' ? `hover:bg-slate-700 ${muted}` : `hover:bg-gray-100 ${muted}`
            }`}
            title="Regenerate summary"
            aria-label="Regenerate summary"
          >
            {regenerating
              ? <Loader2 className="w-3 h-3 animate-spin" />
              : <RefreshCw className="w-3 h-3" />}
          </button>

          {/* Translation dropdown */}
          {languages.length > 0 && (
            <div className="relative">
              <button
                onClick={() => setShowLangMenu(v => !v)}
                disabled={translating || !article.summary}
                className={`p-0.5 rounded transition-colors disabled:opacity-50 ${
                  translatedLang
                    ? theme === 'dark' ? 'text-blue-400 hover:bg-slate-700' : 'text-blue-600 hover:bg-gray-100'
                    : theme === 'dark' ? `hover:bg-slate-700 ${muted}` : `hover:bg-gray-100 ${muted}`
                }`}
                title="Translate summary"
              >
                {translating
                  ? <Loader2 className="w-3 h-3 animate-spin" />
                  : <Languages className="w-3 h-3" />}
              </button>
              {showLangMenu && (
                <div className={`absolute top-full right-0 mt-1 py-1 rounded-lg shadow-lg border z-10 min-w-[120px] ${
                  theme === 'dark' ? 'bg-slate-800 border-slate-600' : 'bg-white border-gray-200'
                }`}>
                  {translatedLang && (
                    <button
                      onClick={clearTranslation}
                      className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                        theme === 'dark' ? 'hover:bg-slate-700 text-slate-300' : 'hover:bg-gray-100 text-slate-700'
                      }`}
                    >
                      Original
                    </button>
                  )}
                  {languages.map(lang => (
                    <button
                      key={lang.code}
                      onClick={() => handleTranslate(lang.code)}
                      className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                        translatedLang === lang.code
                          ? theme === 'dark' ? 'bg-blue-900/40 text-blue-300' : 'bg-blue-50 text-blue-700'
                          : theme === 'dark' ? 'hover:bg-slate-700 text-slate-300' : 'hover:bg-gray-100 text-slate-700'
                      }`}
                    >
                      {lang.native}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div id={`summary-${article.id}`} className={`overflow-hidden transition-all duration-200 ${summaryOpen ? 'max-h-64 mt-2' : 'max-h-0'}`}>
          {article.summary ? (
            <div>
              <p className={`text-xs leading-relaxed ${theme === 'dark' ? 'text-slate-300' : 'text-slate-600'}`}>
                {translatedSummary || article.summary}
              </p>
              {translatedLang && (
                <p className={`text-xs mt-1.5 italic ${theme === 'dark' ? 'text-slate-500' : 'text-slate-400'}`}>
                  Translated to {languages.find(l => l.code === translatedLang)?.name}
                </p>
              )}
            </div>
          ) : (
            <div className="space-y-1.5">
              {[85, 70, 50].map((w, i) => (
                <div
                  key={i}
                  className={`h-2.5 rounded animate-pulse ${theme === 'dark' ? 'bg-slate-700' : 'bg-gray-200'}`}
                  style={{ width: `${w}%` }}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
    </>
  );
}
