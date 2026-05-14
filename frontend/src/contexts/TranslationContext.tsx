import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { newsApi, TranslationLanguage } from '../api/newsApi';

interface TranslationContextType {
  languages: TranslationLanguage[];
  loading: boolean;
}

const TranslationContext = createContext<TranslationContextType>({
  languages: [],
  loading: true,
});

export function TranslationProvider({ children }: { children: ReactNode }) {
  const [languages, setLanguages] = useState<TranslationLanguage[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    newsApi.getTranslationLanguages()
      .then(res => {
        setLanguages(res.languages);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  return (
    <TranslationContext.Provider value={{ languages, loading }}>
      {children}
    </TranslationContext.Provider>
  );
}

export function useTranslation() {
  return useContext(TranslationContext);
}
