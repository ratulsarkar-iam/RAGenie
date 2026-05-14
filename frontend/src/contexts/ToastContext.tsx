import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { CheckCircle, XCircle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info';

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  show: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue>({ show: () => {} });

let _id = 0;

const ICONS = {
  success: <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />,
  error:   <XCircle    className="w-4 h-4 text-red-400 flex-shrink-0" />,
  info:    <Info       className="w-4 h-4 text-blue-400 flex-shrink-0" />,
};

const BG: Record<ToastType, string> = {
  success: 'bg-slate-800 border-emerald-700/50',
  error:   'bg-slate-800 border-red-700/50',
  info:    'bg-slate-800 border-blue-700/50',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) =>
    setToasts(prev => prev.filter(t => t.id !== id)), []);

  const show = useCallback((message: string, type: ToastType = 'info') => {
    const id = ++_id;
    setToasts(prev => [...prev.slice(-4), { id, message, type }]);
    setTimeout(() => dismiss(id), 4000);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      {/* Toast container — fixed bottom-right */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-center gap-2.5 px-3 py-2.5 rounded-xl border shadow-xl
              text-sm text-slate-100 max-w-xs animate-fade-in ${BG[t.type]}`}
          >
            {ICONS[t.type]}
            <span className="flex-1 leading-snug">{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              className="text-slate-400 hover:text-slate-200 transition-colors"
              aria-label="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext).show;
