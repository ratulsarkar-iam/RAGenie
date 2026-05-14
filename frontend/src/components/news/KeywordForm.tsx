import { useState, useRef } from 'react';
import { Sparkles, ArrowLeft, Plus, Loader2, Pencil, Clock, Newspaper } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { useToast } from '../../contexts/ToastContext';
import { newsApi, Keyword } from '../../api/newsApi';

interface Props {
  onCreated: (kw: Keyword) => void;
}

const INTERVALS = [
  { label: '15 min',  value: 15  },
  { label: '30 min',  value: 30  },
  { label: '1 hour',  value: 60  },
  { label: '2 hours', value: 120 },
  { label: '6 hours', value: 360 },
  { label: '24 hrs',  value: 1440},
];
const MAX_ARTICLES = [5, 10, 20, 50];

type Step = 'describe' | 'review';

const EXAMPLES = [
  'West Bengal floods and disaster relief',
  'AI chip companies + semiconductor supply chain',
  'India cricket team upcoming series',
  'climate change renewable energy policy',
];

export default function KeywordForm({ onCreated }: Props) {
  const { theme } = useTheme();
  const toast = useToast();
  const [step, setStep]               = useState<Step>('describe');
  const [description, setDescription] = useState('');
  const [term, setTerm]               = useState('');
  const [explanation, setExplanation] = useState('');
  const [interval, setInterval]       = useState(60);
  const [maxArticles, setMaxArticles] = useState(10);
  const [generating, setGenerating]   = useState(false);
  const [saving, setSaving]           = useState(false);
  const [error, setError]             = useState<string | null>(null);
  const termRef = useRef<HTMLInputElement>(null);

  const isDark = theme === 'dark';

  const inputCls = `w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    isDark ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500'
           : 'bg-white border-gray-300 text-slate-900 placeholder-slate-400'}`;

  const selectCls = `flex-1 px-2 py-1.5 rounded-lg border text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 ${
    isDark ? 'bg-slate-800 border-slate-600 text-white'
           : 'bg-white border-gray-300 text-slate-900'}`;

  const goToReview = (suggestedTerm: string, expl: string) => {
    setTerm(suggestedTerm);
    setExplanation(expl);
    setStep('review');
    setTimeout(() => termRef.current?.focus(), 50);
  };

  const handleGenerate = async () => {
    if (!description.trim()) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await newsApi.suggestKeyword(description);
      goToReview(res.term, res.explanation);
    } catch (e: any) {
      setError(e.message || 'LLM suggestion failed — enter a keyword manually below');
      goToReview(description.trim(), '');
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = async () => {
    const trimmed = term.trim();
    if (!trimmed) return;
    setSaving(true);
    setError(null);
    try {
      const kw = await newsApi.createKeyword({
        term: trimmed,
        fetch_interval_minutes: interval,
        max_articles_per_fetch: maxArticles,
      });
      onCreated(kw);
      toast(`Tracking "${trimmed}"`, 'success');
      setStep('describe');
      setDescription('');
      setTerm('');
      setExplanation('');
    } catch (err: any) {
      setError(
        err.status === 409
          ? `"${trimmed}" is already tracked.`
          : err.message || 'Failed to save keyword',
      );
    } finally {
      setSaving(false);
    }
  };

  const muted = isDark ? 'text-slate-400' : 'text-slate-500';

  // ── Step 1: Describe ──────────────────────────────────────────────────
  if (step === 'describe') {
    return (
      <div className="space-y-3">
        <p className={`text-xs font-medium ${muted}`}>
          Describe what news you want to track
        </p>

        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleGenerate(); }}
          placeholder={`e.g. "${EXAMPLES[Math.floor(Date.now() / 5000) % EXAMPLES.length]}"`}
          rows={3}
          className={`w-full px-3 py-2 rounded-lg border text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 ${
            isDark ? 'bg-slate-800 border-slate-600 text-white placeholder-slate-500'
                   : 'bg-white border-gray-300 text-slate-900 placeholder-slate-400'}`}
        />

        <p className={`text-xs ${muted} opacity-70`}>
          Separate multiple topics with <code className="font-mono">,</code> or <code className="font-mono">+</code>
          &nbsp;· Ctrl+Enter to generate
        </p>

        <div className="flex gap-2">
          <button
            onClick={handleGenerate}
            disabled={generating || !description.trim()}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            {generating
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <Sparkles className="w-3.5 h-3.5" />}
            {generating ? 'Generating…' : 'Generate Keyword'}
          </button>
          <button
            onClick={() => goToReview('', '')}
            className={`px-3 py-2 rounded-lg text-sm transition-colors ${
              isDark ? `${muted} hover:bg-slate-700` : `${muted} hover:bg-gray-100`}`}
            title="Enter keyword manually"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
        </div>

        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
    );
  }

  // ── Step 2: Review & Save ─────────────────────────────────────────────
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <button
          onClick={() => { setStep('describe'); setError(null); }}
          className={`p-1 rounded ${isDark ? `${muted} hover:bg-slate-700` : `${muted} hover:bg-gray-100`}`}
          title="Back"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
        </button>
        <p className={`text-xs font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>
          Review &amp; Save
        </p>
      </div>

      {/* Editable term */}
      <div>
        <label className={`text-xs font-medium ${muted} mb-1 block`}>Search keyword</label>
        <input
          ref={termRef}
          value={term}
          onChange={e => setTerm(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSave(); }}
          placeholder="e.g. West Bengal flood disaster"
          className={inputCls}
        />
      </div>

      {/* LLM explanation */}
      {explanation && (
        <p className={`text-xs rounded-lg px-3 py-2 ${
          isDark ? 'bg-blue-900/30 text-blue-300' : 'bg-blue-50 text-blue-700'
        }`}>
          💡 {explanation}
        </p>
      )}

      {/* Settings row */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className={`text-xs ${muted} flex items-center gap-1 mb-1`}>
            <Clock className="w-3 h-3" /> Fetch every
          </label>
          <select value={interval} onChange={e => setInterval(Number(e.target.value))} className={selectCls}>
            {INTERVALS.map(i => <option key={i.value} value={i.value}>{i.label}</option>)}
          </select>
        </div>
        <div>
          <label className={`text-xs ${muted} flex items-center gap-1 mb-1`}>
            <Newspaper className="w-3 h-3" /> Max articles
          </label>
          <select value={maxArticles} onChange={e => setMaxArticles(Number(e.target.value))} className={selectCls}>
            {MAX_ARTICLES.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      </div>

      <button
        onClick={handleSave}
        disabled={saving || !term.trim()}
        className="w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold transition-colors"
      >
        {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
        {saving ? 'Saving…' : 'Save Keyword'}
      </button>

      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
