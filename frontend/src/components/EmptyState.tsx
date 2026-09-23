import type { ReactNode } from "react";

import { Button } from "@/components/Button";

interface EmptyStateProps {
  /** Illustration slot — an inline SVG (no asset fetch), or any node. */
  illustration?: ReactNode;
  headline: string;
  support?: string;
  /** Label for the primary action button; `onAction` fires on click. */
  actionLabel?: string;
  onAction?: () => void;
}

const DEFAULT_ILLUSTRATION = (
  <svg
    aria-hidden="true"
    viewBox="0 0 64 64"
    className="h-16 w-16 text-slate-300 dark:text-slate-600"
    fill="currentColor"
  >
    <path d="M20 14h24a6 6 0 0 1 6 6v18a6 6 0 0 1-6 6H34l-8 7v-7h-6a6 6 0 0 1-6-6V20a6 6 0 0 1 6-6Z" />
    <circle cx="26" cy="28" r="2.5" className="text-slate-500 dark:text-slate-400" />
    <circle cx="38" cy="28" r="2.5" className="text-slate-500 dark:text-slate-400" />
  </svg>
);

/**
 * 11's "every list needs an empty state": illustration slot, headline,
 * supporting line, and an optional primary action.
 */
export function EmptyState({
  illustration,
  headline,
  support,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-8 text-center" data-testid="empty-state">
      {illustration ?? DEFAULT_ILLUSTRATION}
      <h3 className="text-lg font-semibold">{headline}</h3>
      {support !== undefined && (
        <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm">{support}</p>
      )}
      {actionLabel !== undefined && onAction !== undefined && (
        <Button onClick={onAction}>{actionLabel}</Button>
      )}
    </div>
  );
}
