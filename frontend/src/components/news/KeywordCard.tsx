import { useState, useRef } from 'react';
import { Trash2, RefreshCw, Pause, Play, AlertTriangle, Loader2, Pencil, Check, X, Clock } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { useToast } from '../../contexts/ToastContext';
import { newsApi, Keyword } from '../../api/newsApi';
import ConfirmDialog from '../shared/ConfirmDialog';

interface Props {
  keyword: Keyword;
  selected: boolean;
  newArticles?: number;
  onUpdated: (kw: Keyword) => void;
  onDeleted: (id: string) => void;
  onSelect: (id: string) => void;
}

const INTERVALS = [
  { label: '15 min',  value: 15   },
  { label: '30 min',  value: 30   },
  { label: '1 hour',  value: 60   },
  { label: '2 hours', value: 120  },
  { label: '6 hours', value: 360  },
  { label: '24 hrs',  value: 1440 },
];

function relativeTime(iso: string | null): string {
  if (!iso) return 'Never';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'Just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function KeywordCard({ keyword, selected, newArticles = 0, onUpdated, onDeleted, onSelect }: Props) {
  const { theme } = useTheme();
  const toast = useToast();
  const [fetching, setFetching]     = useState(false);
  const [toggling, setToggling]     = useState(false);
  const [editing, setEditing]       = useState(false);
  const [editTerm, setEditTerm]     = useState('');
  const [editInterval, setEditInterval] = useState(60);
  const [savingTerm, setSavingTerm] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const editRef = useRef<HTMLInputElement>(null);

  const startEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditTerm(keyword.term);
    setEditInterval(keyword.fetch_interval_minutes);
    setEditing(true);
    setTimeout(() => editRef.current?.select(), 30);
  };

  const cancelEdit = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditing(false);
  };

  const saveTerm = async (e?: React.MouseEvent) => {
    e?.stopPropagation();
    const trimmed = editTerm.trim();
    if (!trimmed) { cancelEdit(); return; }
    const termChanged = trimmed !== keyword.term;
    const intervalChanged = editInterval !== keyword.fetch_interval_minutes;
    if (!termChanged && !intervalChanged) { cancelEdit(); return; }
    
    setSavingTerm(true);
    try {
      const payload: any = {};
      if (termChanged) payload.term = trimmed;
      if (intervalChanged) payload.fetch_interval_minutes = editInterval;
      const updated = await newsApi.updateKeyword(keyword.id, payload);
      onUpdated(updated);
      setEditing(false);
    } catch {
      // leave edit mode open on error
    } finally {
      setSavingTerm(false);
    }
  };

  const handleFetchNow = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setFetching(true);
    toast(`Fetching news for "${keyword.term}"…`, 'info');
    try {
      await newsApi.fetchNow(keyword.id);
      setTimeout(async () => {
        try {
          const kws = await newsApi.getKeywords();
          const updated = kws.find(k => k.id === keyword.id);
          if (updated) onUpdated(updated);
        } finally {
          setFetching(false);
        }
      }, 2000);
    } catch {
      toast('Fetch failed', 'error');
      setFetching(false);
    }
  };

  const handleToggle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setToggling(true);
    try {
      const updated = await newsApi.updateKeyword(keyword.id, { enabled: !keyword.enabled });
      onUpdated(updated);
      toast(`"${keyword.term}" ${!keyword.enabled ? 'resumed' : 'paused'}`, 'info');
    } catch {
      toast('Failed to update keyword', 'error');
    } finally {
      setToggling(false);
    }
  };

  const handleDelete = async () => {
    try {
      await newsApi.deleteKeyword(keyword.id);
      onDeleted(keyword.id);
      toast(`Stopped tracking "${keyword.term}"`, 'info');
    } catch {
      toast('Failed to delete keyword', 'error');
    }
  };

  const cardClass = `p-3 rounded-xl border cursor-pointer transition-all ${
    selected
      ? theme === 'dark'
        ? 'bg-blue-900/40 border-blue-600'
        : 'bg-blue-50 border-blue-400'
      : theme === 'dark'
      ? 'bg-slate-800/50 border-slate-700 hover:bg-slate-800'
      : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
  }`;

  const iconBtn = (dark: string, light: string) =>
    `p-1.5 rounded-lg transition-colors disabled:opacity-50 ${
      theme === 'dark' ? dark : light
    }`;

  return (
    <>
    <ConfirmDialog
      open={confirmDelete}
      title="Delete keyword"
      message={`Delete "${keyword.term}" and all ${keyword.article_count} article${keyword.article_count !== 1 ? 's' : ''}? This cannot be undone.`}
      confirmLabel="Delete"
      danger
      onConfirm={() => { setConfirmDelete(false); handleDelete(); }}
      onCancel={() => setConfirmDelete(false)}
    />
    <div className={cardClass} onClick={() => !editing && onSelect(keyword.id)}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">

          {/* Term row — normal or edit mode */}
          {editing ? (
            <div className="space-y-2" onClick={e => e.stopPropagation()}>
              <div className="flex items-center gap-1">
                <input
                  ref={editRef}
                  value={editTerm}
                  onChange={e => setEditTerm(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter')  saveTerm();
                    if (e.key === 'Escape') cancelEdit();
                  }}
                  placeholder="Keyword term"
                  className={`flex-1 min-w-0 px-2 py-0.5 rounded border text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 ${
                    theme === 'dark'
                      ? 'bg-slate-700 border-slate-500 text-white'
                      : 'bg-white border-gray-300 text-slate-900'
                  }`}
                />
                <button onClick={saveTerm} disabled={savingTerm}
                  className={iconBtn('hover:bg-green-900/30 text-green-400','hover:bg-green-50 text-green-600')}>
                  {savingTerm ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                </button>
                <button onClick={cancelEdit}
                  className={iconBtn('hover:bg-slate-700 text-slate-400','hover:bg-gray-200 text-slate-500')}>
                  <X className="w-3 h-3" />
                </button>
              </div>
              <div className="flex items-center gap-1.5">
                <label className={`text-xs flex items-center gap-1 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
                  <Clock className="w-3 h-3" /> Fetch every
                </label>
                <select
                  value={editInterval}
                  onChange={e => setEditInterval(Number(e.target.value))}
                  className={`flex-1 px-2 py-0.5 rounded border text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 ${
                    theme === 'dark'
                      ? 'bg-slate-700 border-slate-500 text-white'
                      : 'bg-white border-gray-300 text-slate-900'
                  }`}
                >
                  {INTERVALS.map(i => (
                    <option key={i.value} value={i.value}>{i.label}</option>
                  ))}
                </select>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-1.5">
              <p className={`text-sm font-medium truncate ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>
                {keyword.term}
              </p>
              {newArticles > 0 && (
                <span className="flex-shrink-0 px-1.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500 text-white leading-none">
                  +{newArticles}
                </span>
              )}
              {keyword.last_error && (
                <span title={keyword.last_error}>
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                </span>
              )}
            </div>
          )}

          <div className={`flex flex-wrap items-center gap-2 mt-1 text-xs ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>
            <span className={`px-1.5 py-0.5 rounded-full font-medium ${
              keyword.enabled
                ? 'bg-emerald-500/20 text-emerald-500'
                : 'bg-slate-500/20 text-slate-500'
            }`}>
              {keyword.enabled ? 'Active' : 'Paused'}
            </span>
            <span>{keyword.article_count} articles</span>
            <span>{INTERVALS.find(i => i.value === keyword.fetch_interval_minutes)?.label ?? `${keyword.fetch_interval_minutes}m`}</span>
            <span>{relativeTime(keyword.last_fetched_at)}</span>
          </div>
        </div>

        {!editing && (
          <div className="flex items-center gap-0.5">
            <button
              onClick={startEdit}
              className={iconBtn('hover:bg-slate-700 text-slate-400', 'hover:bg-gray-200 text-slate-600')}
              title="Edit keyword"
              aria-label={`Edit keyword: ${keyword.term}`}
            >
              <Pencil className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleFetchNow}
              disabled={fetching}
              className={iconBtn('hover:bg-slate-700 text-slate-400', 'hover:bg-gray-200 text-slate-600')}
              title="Fetch now"
              aria-label={`Fetch news now for: ${keyword.term}`}
            >
              {fetching
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <RefreshCw className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={handleToggle}
              disabled={toggling}
              className={iconBtn('hover:bg-slate-700 text-slate-400', 'hover:bg-gray-200 text-slate-600')}
              title={keyword.enabled ? 'Pause' : 'Resume'}
              aria-label={`${keyword.enabled ? 'Pause' : 'Resume'} keyword: ${keyword.term}`}
            >
              {toggling
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : keyword.enabled
                ? <Pause className="w-3.5 h-3.5" />
                : <Play className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={e => { e.stopPropagation(); setConfirmDelete(true); }}
              className={`p-1.5 rounded-lg transition-colors ${
                theme === 'dark'
                  ? 'hover:bg-red-900/30 text-red-400'
                  : 'hover:bg-red-50 text-red-500'
              }`}
              title="Delete keyword"
              aria-label={`Delete keyword: ${keyword.term}`}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
    </>
  );
}
