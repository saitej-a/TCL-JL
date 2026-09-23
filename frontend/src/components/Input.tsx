import { useId, useState, type InputHTMLAttributes, type ReactNode } from "react";

const CONTROL_CLASSES =
  "w-full h-10 px-3.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition-all";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  helperText?: string;
  errorText?: string;
}

/** §6.2.1: label + control + helper/error, with aria wiring for announcement. */
export function Input({
  label,
  helperText,
  errorText,
  type = "text",
  className = "",
  id,
  ...rest
}: InputProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const helperId = helperText !== undefined ? `${inputId}-helper` : undefined;
  const errorId = errorText !== undefined ? `${inputId}-error` : undefined;
  const describedBy =
    [errorId, helperId].filter(Boolean).join(" ") || undefined;

  const isPassword = type === "password";
  const [revealed, setRevealed] = useState(false);
  const effectiveType = isPassword && revealed ? "text" : type;

  return (
    <div className="flex flex-col gap-1.5">
      {label !== undefined && (
        <label
          htmlFor={inputId}
          className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center justify-between"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <input
          id={inputId}
          type={effectiveType}
          className={`${CONTROL_CLASSES} ${isPassword ? "pr-10" : ""} ${className}`.trim()}
          aria-invalid={errorText !== undefined}
          aria-describedby={describedBy}
          {...rest}
        />
        {isPassword && (
          <button
            type="button"
            aria-label="Toggle password visibility"
            aria-pressed={revealed}
            onClick={() => setRevealed((current) => !current)}
            className="absolute right-2 top-1/2 -translate-y-1/2 h-8 w-8 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 focus:outline-none"
          >
            {revealed ? "🙈" : "👁"}
          </button>
        )}
      </div>
      {errorText !== undefined && (
        <p id={errorId} className="text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1 font-medium mt-0.5">
          <ErrorGlyph /> {errorText}
        </p>
      )}
      {helperText !== undefined && (
        <p id={helperId} className="text-xs text-slate-500 dark:text-slate-400">
          {helperText}
        </p>
      )}
    </div>
  );
}

function ErrorGlyph(): ReactNode {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" className="h-3.5 w-3.5 fill-current">
      <path d="M8 1.5 15 14H1L8 1.5Zm0 4.5a.75.75 0 0 0-.75.75v3a.75.75 0 0 0 1.5 0v-3A.75.75 0 0 0 8 6Zm0 6a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z" />
    </svg>
  );
}
