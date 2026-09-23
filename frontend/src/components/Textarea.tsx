import { useId, type TextareaHTMLAttributes } from "react";

const TEXTAREA_CLASSES =
  "w-full px-3.5 py-2.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition-all";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  helperText?: string;
  errorText?: string;
  /** §6.2.1 defaults: 5000 for posts, 2000 for comments. */
  maxLength?: number;
}

/** §6.2.1's textarea with the live `N / M characters` tally. */
export function Textarea({
  label,
  helperText,
  errorText,
  maxLength,
  value,
  onChange,
  className = "",
  id,
  ...rest
}: TextareaProps) {
  const autoId = useId();
  const textareaId = id ?? autoId;
  const helperId = helperText !== undefined ? `${textareaId}-helper` : undefined;
  const errorId = errorText !== undefined ? `${textareaId}-error` : undefined;
  const describedBy =
    [errorId, helperId].filter(Boolean).join(" ") || undefined;

  const currentLength = typeof value === "string" ? value.length : 0;
  const ratio = maxLength !== undefined && maxLength > 0 ? currentLength / maxLength : 0;
  const tallyClass =
    ratio > 1
      ? "text-rose-600 dark:text-rose-400"
      : ratio >= 0.9
        ? "text-amber-600 dark:text-amber-400"
        : "text-slate-500 dark:text-slate-400";

  return (
    <div className="flex flex-col gap-1.5">
      {label !== undefined && (
        <label
          htmlFor={textareaId}
          className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center justify-between"
        >
          {label}
        </label>
      )}
      <textarea
        id={textareaId}
        value={value}
        onChange={onChange}
        maxLength={maxLength}
        className={`${TEXTAREA_CLASSES} ${className}`.trim()}
        aria-invalid={errorText !== undefined}
        aria-describedby={describedBy}
        {...rest}
      />
      {maxLength !== undefined && (
        <p className={`text-xs text-right ${tallyClass}`} aria-live="polite">
          {currentLength.toLocaleString()} / {maxLength.toLocaleString()} characters
        </p>
      )}
      {errorText !== undefined && (
        <p id={errorId} className="text-xs text-rose-600 dark:text-rose-400 flex items-center gap-1 font-medium mt-0.5">
          {errorText}
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
