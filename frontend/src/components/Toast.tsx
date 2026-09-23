import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type ToastVariant = "success" | "error" | "info";

/** §6.7.1's exact variant classes (dark surfaces, per-variant borders). */
const VARIANT_CLASSES: Record<ToastVariant, string> = {
  success: "bg-emerald-900/90 text-emerald-100 border border-emerald-700",
  error: "bg-rose-900/90 text-rose-100 border border-rose-700",
  info: "bg-slate-900/90 text-slate-100 border border-slate-700",
};

const VARIANT_ROLE: Record<ToastVariant, "status" | "alert"> = {
  success: "status",
  info: "status",
  error: "alert",
};

/** §6.7.1: automatic fade-out after 4,000 ms; pauses on hover/focus. */
const TOAST_DURATION_MS = 4_000;

export interface ToastOptions {
  message: string;
  variant?: ToastVariant;
}

interface ToastEntry extends Required<ToastOptions> {
  id: number;
  /** Paused remaining time bookkeeping. */
  remainingMs: number;
  startedAt: number;
}

interface ToastContextValue {
  toast: (options: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((entry) => entry.id !== id));
  }, []);

  const toast = useCallback(
    ({ message, variant = "info" }: ToastOptions) => {
      const id = nextId.current;
      nextId.current += 1;
      setToasts((current) => [
        ...current,
        { id, message, variant, remainingMs: TOAST_DURATION_MS, startedAt: Date.now() },
      ]);
    },
    [],
  );

  const value = useMemo<ToastContextValue>(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* Desktop: bottom-right. Mobile: top-center (§6.7.1). */}
      <div className="fixed bottom-6 right-6 top-auto max-sm:top-4 max-sm:bottom-auto max-sm:left-4 max-sm:right-4 z-50 flex flex-col gap-2 max-sm:items-center">
        {toasts.map((entry) => (
          <ToastItem key={entry.id} entry={entry} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastItem({
  entry,
  onDismiss,
}: {
  entry: ToastEntry;
  onDismiss: (id: number) => void;
}) {
  // §6.7.1: the 4s timer genuinely pauses on hover/focus — the pending
  // timeout is cancelled and restarted with the REMAINING time on resume.
  const timerRef = useRef<number | null>(null);
  const remainingRef = useRef(TOAST_DURATION_MS);
  const startedAtRef = useRef(0);

  const startTimer = useCallback(() => {
    startedAtRef.current = Date.now();
    timerRef.current = window.setTimeout(() => onDismiss(entry.id), remainingRef.current);
  }, [entry.id, onDismiss]);

  const pauseTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
      remainingRef.current = Math.max(
        remainingRef.current - (Date.now() - startedAtRef.current),
        0,
      );
    }
  }, []);

  useEffect(() => {
    startTimer();
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, [startTimer]);

  return (
    <div
      role={VARIANT_ROLE[entry.variant]}
      className={`${VARIANT_CLASSES[entry.variant]} rounded-lg shadow-lg px-4 py-3 text-sm flex items-center gap-3 min-w-[280px] max-sm:min-w-0 max-sm:w-full`}
      onMouseEnter={pauseTimer}
      onMouseLeave={startTimer}
      onFocus={pauseTimer}
      onBlur={startTimer}
      data-testid="toast"
    >
      <span className="flex-1">{entry.message}</span>
      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={() => onDismiss(entry.id)}
        className="shrink-0 opacity-70 hover:opacity-100 focus:outline-none"
      >
        ×
      </button>
    </div>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (context === null) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
