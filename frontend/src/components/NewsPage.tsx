import { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { TranslationProvider } from '../contexts/TranslationContext';
import { ToastProvider } from '../contexts/ToastContext';
import { Keyword, ArticleWithSummary } from '../api/newsApi';
import KeywordPanel from './news/KeywordPanel';
import ArticleFeed from './news/ArticleFeed';
import ArticleDetailModal from './news/ArticleDetailModal';

export default function NewsPage() {
  const { theme } = useTheme();
  const [selectedKeyword, setSelectedKeyword] = useState<Keyword | null>(null);
  const [detailArticle, setDetailArticle] = useState<ArticleWithSummary | null>(null);
  const [showPanel, setShowPanel] = useState(false);

  const handleUpdatedDetail = (updated: ArticleWithSummary) => {
    setDetailArticle(updated);
  };

  return (
    <ToastProvider>
      <TranslationProvider>
        <div className={`flex h-full overflow-hidden relative ${theme === 'dark' ? 'text-white' : 'text-slate-900'}`}>

          {/* Mobile backdrop */}
          {showPanel && (
            <div
              className="absolute inset-0 z-20 bg-black/50 sm:hidden"
              onClick={() => setShowPanel(false)}
            />
          )}

          {/* Keyword panel — full sidebar on sm+, slide-in overlay on mobile */}
          <aside className={`
            flex-shrink-0 flex flex-col overflow-hidden
            absolute inset-y-0 left-0 z-30 w-72 transition-transform duration-300
            sm:relative sm:translate-x-0
            ${showPanel ? 'translate-x-0' : '-translate-x-full sm:translate-x-0'}
          `}>
            <KeywordPanel
              selectedKeywordId={selectedKeyword?.id ?? null}
              onSelect={kw => { setSelectedKeyword(kw); setShowPanel(false); }}
            />
          </aside>

          <main className="flex-1 overflow-hidden min-w-0">
            <ArticleFeed
              selectedKeyword={selectedKeyword}
              onOpenDetail={setDetailArticle}
              onMenuToggle={() => setShowPanel(v => !v)}
            />
          </main>

          <ArticleDetailModal
            article={detailArticle}
            onClose={() => setDetailArticle(null)}
            onUpdated={handleUpdatedDetail}
          />
        </div>
      </TranslationProvider>
    </ToastProvider>
  );
}
