import { useEffect, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

interface Props {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({
  open, title, message, confirmLabel = 'Confirm', danger = false,
  onConfirm, onCancel,
}: Props) {
  const { theme } = useTheme();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open) {
      el.showModal();
      cancelRef.current?.focus();
    } else {
      el.close();
    }
  }, [open]);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    const onClose = () => onCancel();
    el.addEventListener('cancel', onClose);
    return () => el.removeEventListener('cancel', onClose);
  }, [onCancel]);

  const isDark = theme === 'dark';

  return (
    <dialog
      ref={dialogRef}
      aria-modal="true"
      aria-labelledby="confirm-title"
      onClick={e => { if (e.target === dialogRef.current) onCancel(); }}
      className={`rounded-2xl border p-6 shadow-2xl max-w-sm w-full backdrop:bg-black/50
        ${isDark ? 'bg-slate-800 border-slate-700 text-white' : 'bg-white border-gray-200 text-slate-900'}`}
    >
      <div className="flex gap-3 items-start">
        <AlertTriangle className={`w-5 h-5 mt-0.5 flex-shrink-0 ${danger ? 'text-red-400' : 'text-amber-400'}`} />
        <div className="flex-1">
          <h3 id="confirm-title" className="font-semibold text-sm">{title}</h3>
          <p className={`mt-1 text-sm ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>{message}</p>
        </div>
      </div>
      <div className="flex justify-end gap-2 mt-5">
        <button
          ref={cancelRef}
          onClick={onCancel}
          className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
            isDark ? 'hover:bg-slate-700 text-slate-300' : 'hover:bg-gray-100 text-slate-600'
          }`}
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            danger
              ? 'bg-red-600 hover:bg-red-700 text-white'
              : 'bg-blue-600 hover:bg-blue-700 text-white'
          }`}
        >
          {confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
