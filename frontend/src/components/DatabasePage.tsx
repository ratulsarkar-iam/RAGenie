import { useState, useEffect, useRef, useCallback } from 'react';
import type { KeyboardEvent } from 'react';
import {
  Database, Table2, RefreshCw, Play, Trash2, Copy, Download,
  ChevronDown, ChevronRight, AlertCircle, Clock, List, Key,
  CheckCircle2, Loader2,
} from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

const API = 'http://localhost:8000';

interface DbTable   { name: string; row_count: number }
interface SchemaCol { cid: number; name: string; type: string; notnull: boolean; default: any; pk: boolean }
interface SchemaIdx { name: string; unique: boolean }
interface TableSchema { columns: SchemaCol[]; indexes: SchemaIdx[] }

interface QueryResult {
  columns: string[];
  rows: any[][];
  rowcount: number;
  affected: number;
  duration_ms: number;
}

async function apiFetch<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

const QUICK_QUERIES = [
  { label: 'Tables', sql: "SELECT name, type FROM sqlite_master WHERE type='table' ORDER BY name;" },
  { label: 'Indexes', sql: "SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index' ORDER BY tbl_name;" },
  { label: 'DB Size', sql: "SELECT page_count * page_size / 1024.0 AS size_kb FROM pragma_page_count(), pragma_page_size();" },
];

export default function DatabasePage() {
  const { theme } = useTheme();
  const [dbFiles, setDbFiles]   = useState<string[]>([]);
  const [selectedDb, setSelectedDb] = useState('');
  const [tables, setTables]         = useState<DbTable[]>([]);
  const [expanded, setExpanded]     = useState<string | null>(null);
  const [schemas, setSchemas]       = useState<Record<string, TableSchema>>({});
  const [sql, setSql]               = useState('');
  const [result, setResult]         = useState<QueryResult | null>(null);
  const [error, setError]           = useState<string | null>(null);
  const [running, setRunning]       = useState(false);
  const [loadingTables, setLoadingTables] = useState(false);
  const [copied, setCopied]         = useState(false);
  const editorRef = useRef<HTMLTextAreaElement>(null);

  const isDark  = theme === 'dark';
  const bg      = isDark ? 'bg-slate-900'  : 'bg-gray-50';
  const panel   = isDark ? 'bg-slate-800'  : 'bg-white';
  const border  = isDark ? 'border-slate-700' : 'border-gray-200';
  const muted   = isDark ? 'text-slate-400'   : 'text-slate-500';
  const text    = isDark ? 'text-slate-100'   : 'text-slate-900';
  const hover   = isDark ? 'hover:bg-slate-700/60' : 'hover:bg-gray-50';

  // ── Load DB files ────────────────────────────────────────────────
  useEffect(() => {
    apiFetch<{ files: string[] }>('/api/db/files').then(d => {
      setDbFiles(d.files);
      if (d.files.length > 0) setSelectedDb(d.files[0]);
    }).catch(() => {});
  }, []);

  // ── Load tables when DB changes ──────────────────────────────────
  const loadTables = useCallback(async (db: string) => {
    if (!db) return;
    setLoadingTables(true);
    setTables([]);
    setExpanded(null);
    setSchemas({});
    try {
      const d = await apiFetch<{ tables: DbTable[] }>(
        `/api/db/tables?db=${encodeURIComponent(db)}`
      );
      setTables(d.tables);
    } catch {}
    setLoadingTables(false);
  }, []);

  useEffect(() => { loadTables(selectedDb); }, [selectedDb, loadTables]);

  // ── Schema expand ─────────────────────────────────────────────────
  const toggleExpand = async (name: string) => {
    if (expanded === name) { setExpanded(null); return; }
    setExpanded(name);
    if (schemas[name]) return;
    try {
      const d = await apiFetch<TableSchema>(
        `/api/db/schema?db=${encodeURIComponent(selectedDb)}&table=${encodeURIComponent(name)}`
      );
      setSchemas(prev => ({ ...prev, [name]: d }));
    } catch {}
  };

  // ── Click table name → inject SELECT ─────────────────────────────
  const previewTable = (name: string) => {
    setSql(`SELECT * FROM "${name}" LIMIT 100;`);
    editorRef.current?.focus();
  };

  // ── Execute SQL ───────────────────────────────────────────────────
  const runQuery = useCallback(async () => {
    const q = sql.trim();
    if (!q || !selectedDb) return;
    setRunning(true);
    setResult(null);
    setError(null);
    try {
      const data = await apiFetch<QueryResult>('/api/db/query', {
        method: 'POST',
        body: JSON.stringify({ db: selectedDb, sql: q }),
      });
      setResult(data);
    } catch (e: any) {
      setError(e.message);
    }
    setRunning(false);
  }, [sql, selectedDb]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runQuery();
    }
  };

  // ── Copy CSV ──────────────────────────────────────────────────────
  const copyCSV = () => {
    if (!result) return;
    const esc = (v: any) => {
      const s = v === null ? '' : String(v);
      return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [result.columns.map(esc).join(','),
      ...result.rows.map(r => r.map(esc).join(','))].join('\n');
    navigator.clipboard.writeText(csv);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ── Download CSV ──────────────────────────────────────────────────
  const downloadCSV = () => {
    if (!result) return;
    const esc = (v: any) => {
      const s = v === null ? '' : String(v);
      return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const csv = [result.columns.map(esc).join(','),
      ...result.rows.map(r => r.map(esc).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(blob),
      download: `query_result_${Date.now()}.csv`,
    });
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const lineCount = sql.split('\n').length;

  // ── Render ────────────────────────────────────────────────────────
  return (
    <div className={`flex flex-col h-full overflow-hidden ${bg} ${text}`}>

      {/* ── Top bar ─────────────────────────────────────────────── */}
      <div className={`flex items-center gap-3 px-4 py-2.5 border-b flex-shrink-0 ${panel} ${border}`}>
        <Database className="w-4 h-4 text-blue-500 flex-shrink-0" />
        <span className="font-semibold text-sm">Database Viewer</span>
        <span className={`text-xs px-2 py-0.5 rounded font-medium ${
          isDark ? 'bg-amber-500/20 text-amber-400' : 'bg-amber-50 text-amber-700 border border-amber-200'
        }`}>
          ⚠ Dev Tool — all SQL executed directly on the file
        </span>

        <div className="flex-1" />

        {/* Quick queries */}
        <div className="flex items-center gap-1">
          {QUICK_QUERIES.map(q => (
            <button
              key={q.label}
              onClick={() => { setSql(q.sql); editorRef.current?.focus(); }}
              className={`text-xs px-2 py-1 rounded transition-colors ${
                isDark ? `${muted} hover:bg-slate-700` : `${muted} hover:bg-gray-100`
              }`}
            >
              {q.label}
            </button>
          ))}
        </div>

        {/* DB selector */}
        <select
          value={selectedDb}
          onChange={e => setSelectedDb(e.target.value)}
          className={`text-xs px-3 py-1.5 rounded-lg border font-mono max-w-xs ${
            isDark ? 'bg-slate-700 border-slate-600 text-slate-200' : 'bg-white border-gray-300 text-slate-700'
          }`}
        >
          {dbFiles.map(f => <option key={f} value={f}>{f}</option>)}
          {dbFiles.length === 0 && <option disabled>No .db files found in data/</option>}
        </select>

        <button
          onClick={() => loadTables(selectedDb)}
          disabled={loadingTables}
          className={`p-1.5 rounded-lg transition-colors ${
            isDark ? `${muted} hover:bg-slate-700` : `${muted} hover:bg-gray-100`
          }`}
          title="Refresh tables"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loadingTables ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* ── Body ────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── Left sidebar: Table browser ─────────────────────── */}
        <aside className={`w-60 flex-shrink-0 border-r flex flex-col overflow-hidden ${border}`}>
          <div className={`px-3 py-2 border-b text-xs font-semibold uppercase tracking-wider flex items-center justify-between ${muted} ${border}`}>
            <span>Tables ({tables.length})</span>
            {loadingTables && <Loader2 className="w-3 h-3 animate-spin" />}
          </div>

          <div className="flex-1 overflow-y-auto py-1">
            {tables.length === 0 && !loadingTables && (
              <p className={`text-xs text-center py-10 ${muted}`}>
                {selectedDb ? 'No tables found' : 'Select a database'}
              </p>
            )}

            {tables.map(t => (
              <div key={t.name}>
                {/* Table row */}
                <div className={`flex items-center gap-0.5 px-1.5 py-1 ${hover} cursor-pointer transition-colors`}>
                  {/* Expand toggle */}
                  <button
                    onClick={() => toggleExpand(t.name)}
                    className={`p-0.5 rounded ${muted}`}
                  >
                    {expanded === t.name
                      ? <ChevronDown className="w-3 h-3" />
                      : <ChevronRight className="w-3 h-3" />}
                  </button>

                  {/* Table name → click to preview */}
                  <button
                    onClick={() => previewTable(t.name)}
                    className="flex-1 flex items-center gap-1.5 min-w-0 text-left"
                    title={`SELECT * FROM "${t.name}" LIMIT 100`}
                  >
                    <Table2 className="w-3 h-3 text-blue-400 flex-shrink-0" />
                    <span className={`text-xs font-mono truncate ${text}`}>{t.name}</span>
                    <span className={`ml-auto text-xs flex-shrink-0 tabular-nums ${muted}`}>
                      {t.row_count >= 0 ? t.row_count : '?'}
                    </span>
                  </button>
                </div>

                {/* Column list */}
                {expanded === t.name && (
                  <div className={`ml-6 border-l pb-1 ${border}`}>
                    {schemas[t.name] ? (
                      <>
                        {schemas[t.name].columns.map(col => (
                          <div
                            key={col.name}
                            className="flex items-center gap-1 px-2 py-0.5"
                            title={`${col.type}${col.notnull ? ' NOT NULL' : ''}${col.default != null ? ` DEFAULT ${col.default}` : ''}`}
                          >
                            {col.pk
                              ? <Key className="w-2.5 h-2.5 text-amber-400 flex-shrink-0" />
                              : <span className={`w-2.5 h-2.5 flex-shrink-0`} />}
                            <span className={`text-xs font-mono truncate ${
                              col.pk
                                ? isDark ? 'text-amber-400' : 'text-amber-600'
                                : text
                            }`}>
                              {col.name}
                            </span>
                            <span className={`ml-auto text-xs font-mono flex-shrink-0 ${muted} opacity-70`}>
                              {col.type}
                            </span>
                          </div>
                        ))}
                        {schemas[t.name].indexes.length > 0 && (
                          <div className={`mt-0.5 px-2 pt-1 border-t ${border}`}>
                            {schemas[t.name].indexes.map(idx => (
                              <div key={idx.name} className={`text-xs ${muted} flex items-center gap-1`}>
                                <span className="opacity-60">IDX</span>
                                <span className="font-mono truncate">{idx.name}</span>
                                {idx.unique && <span className="text-blue-400 text-xs">UNIQUE</span>}
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    ) : (
                      <p className={`text-xs py-1.5 px-2 ${muted}`}>
                        <Loader2 className="w-3 h-3 animate-spin inline mr-1" />Loading…
                      </p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </aside>

        {/* ── Right: Editor + Results ──────────────────────────── */}
        <div className="flex-1 min-w-0 flex flex-col overflow-hidden">

          {/* ── SQL Editor ────────────────────────────────────── */}
          <div className={`border-b flex-shrink-0 ${border}`} style={{ minHeight: 170 }}>
            {/* Editor toolbar */}
            <div className={`flex items-center gap-2 px-3 py-1.5 border-b ${border} ${isDark ? 'bg-slate-800/80' : 'bg-gray-50'}`}>
              <span className={`text-xs font-semibold ${muted}`}>SQL Editor</span>
              <span className={`text-xs ${muted}`}>{lineCount} line{lineCount !== 1 ? 's' : ''}</span>
              <div className="flex-1" />
              <button
                onClick={() => { setSql(''); setResult(null); setError(null); }}
                className={`flex items-center gap-1 text-xs px-2 py-1 rounded transition-colors ${
                  isDark ? `${muted} hover:bg-slate-700` : `${muted} hover:bg-gray-200`
                }`}
              >
                <Trash2 className="w-3 h-3" /> Clear
              </button>
              <button
                onClick={runQuery}
                disabled={running || !sql.trim() || !selectedDb}
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-semibold transition-colors disabled:opacity-40 ${
                  isDark
                    ? 'bg-green-600 hover:bg-green-500 text-white'
                    : 'bg-green-500 hover:bg-green-600 text-white'
                }`}
              >
                {running
                  ? <Loader2 className="w-3 h-3 animate-spin" />
                  : <Play className="w-3 h-3" />}
                {running ? 'Running…' : 'Run'}
                <kbd className="text-xs opacity-60 font-normal ml-0.5">Ctrl+↵</kbd>
              </button>
            </div>

            {/* Textarea */}
            <textarea
              ref={editorRef}
              value={sql}
              onChange={e => setSql(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={"-- Type SQL here, e.g.:\nSELECT * FROM articles LIMIT 50;\n\n-- Click a table name on the left to auto-fill a SELECT"}
              spellCheck={false}
              autoCapitalize="off"
              autoCorrect="off"
              className={`w-full resize-none p-4 font-mono text-sm outline-none leading-relaxed ${
                isDark
                  ? 'bg-slate-900 text-emerald-300 placeholder-slate-600 caret-emerald-400'
                  : 'bg-white text-slate-800 placeholder-gray-400'
              }`}
              style={{ height: 140 }}
            />
          </div>

          {/* ── Results ───────────────────────────────────────── */}
          <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
            {/* Results toolbar */}
            <div className={`flex items-center gap-2 px-3 py-1.5 border-b text-xs flex-shrink-0 ${isDark ? 'bg-slate-800/60' : 'bg-gray-50'} ${border}`}>
              <span className={`font-semibold ${muted}`}>Results</span>

              {result && (
                <>
                  <span className={`flex items-center gap-1 px-2 py-0.5 rounded-full ${
                    isDark ? 'bg-green-500/20 text-green-400' : 'bg-green-50 text-green-700 border border-green-200'
                  }`}>
                    <List className="w-3 h-3" />
                    {result.columns.length > 0
                      ? `${result.rowcount} row${result.rowcount !== 1 ? 's' : ''}`
                      : `${result.affected} row${result.affected !== 1 ? 's' : ''} affected`}
                  </span>
                  <span className={`flex items-center gap-1 ${muted}`}>
                    <Clock className="w-3 h-3" />
                    {result.duration_ms}ms
                  </span>
                  <span className={`${muted}`}>·</span>
                  <span className={`${muted}`}>{result.columns.length} col{result.columns.length !== 1 ? 's' : ''}</span>
                  <div className="flex-1" />
                  <button
                    onClick={copyCSV}
                    className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                      isDark ? `${muted} hover:bg-slate-700` : `${muted} hover:bg-gray-200`
                    }`}
                    title="Copy as CSV"
                  >
                    {copied ? <CheckCircle2 className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                    {copied ? 'Copied!' : 'Copy CSV'}
                  </button>
                  <button
                    onClick={downloadCSV}
                    className={`flex items-center gap-1 px-2 py-0.5 rounded transition-colors ${
                      isDark ? `${muted} hover:bg-slate-700` : `${muted} hover:bg-gray-200`
                    }`}
                    title="Download as CSV"
                  >
                    <Download className="w-3 h-3" /> Download
                  </button>
                </>
              )}

              {error && (
                <span className={`flex items-center gap-1 ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                  <AlertCircle className="w-3 h-3" /> Error
                </span>
              )}
            </div>

            {/* Results body */}
            <div className="flex-1 min-w-0 overflow-x-auto overflow-y-auto">
              {/* Error box */}
              {error && (
                <div className={`m-4 p-3 rounded-lg border font-mono text-xs whitespace-pre-wrap ${
                  isDark ? 'bg-red-950/40 border-red-800/60 text-red-300' : 'bg-red-50 border-red-200 text-red-700'
                }`}>
                  {error}
                </div>
              )}

              {/* Non-SELECT success */}
              {result && result.columns.length === 0 && (
                <div className={`m-4 flex items-center gap-2 text-sm ${isDark ? 'text-green-400' : 'text-green-700'}`}>
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  Query executed successfully — {result.affected} row{result.affected !== 1 ? 's' : ''} affected
                  <span className={`text-xs ${muted}`}>({result.duration_ms}ms)</span>
                </div>
              )}

              {/* Data grid */}
              {result && result.columns.length > 0 && (
                <table className="text-xs border-collapse min-w-max">
                  <thead className={`sticky top-0 z-10 ${isDark ? 'bg-slate-800' : 'bg-gray-100'}`}>
                    <tr>
                      <th className={`px-2 py-2 text-right font-mono select-none border-b border-r w-10 ${muted} ${border}`}>
                        #
                      </th>
                      {result.columns.map(col => (
                        <th
                          key={col}
                          className={`px-3 py-2 text-left font-mono font-semibold whitespace-nowrap border-b border-r ${border} ${text}`}
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr
                        key={i}
                        className={`border-b ${border} transition-colors ${
                          i % 2 === 0
                            ? isDark ? 'bg-slate-900' : 'bg-white'
                            : isDark ? 'bg-slate-800/30' : 'bg-gray-50/70'
                        } ${isDark ? 'hover:bg-slate-700/40' : 'hover:bg-blue-50/50'}`}
                      >
                        <td className={`px-2 py-1.5 text-right font-mono select-none border-r ${border} ${muted} tabular-nums`}>
                          {i + 1}
                        </td>
                        {row.map((cell, j) => (
                          <td
                            key={j}
                            title={cell === null ? 'NULL' : String(cell)}
                            className={`px-3 py-1.5 font-mono whitespace-nowrap border-r max-w-xs truncate ${border} ${
                              cell === null
                                ? isDark ? 'text-slate-600 italic' : 'text-gray-400 italic'
                                : typeof cell === 'number'
                                  ? isDark ? 'text-sky-300' : 'text-sky-700'
                                  : typeof cell === 'string' && (cell.startsWith('http') || cell.startsWith('data:'))
                                    ? isDark ? 'text-purple-300' : 'text-purple-700'
                                    : text
                            }`}
                          >
                            {cell === null ? 'NULL' : String(cell)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {/* Empty state */}
              {!result && !error && !running && (
                <div className={`flex flex-col items-center justify-center h-full py-20 gap-3 ${muted}`}>
                  <Database className="w-10 h-10 opacity-20" />
                  <p className="text-sm">Run a query or click a table name to preview its data</p>
                  <p className="text-xs opacity-60">Ctrl+Enter to execute</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
