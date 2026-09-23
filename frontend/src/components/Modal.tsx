import {
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";

import { SURFACES } from "@/theme/tokens";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  /** Accessible name for the dialog (rendered as the heading). */
  title: string;
  children: ReactNode;
}

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * §6.6: a desktop centered dialog (max-w-md) that presents as a bottom sheet
 * below 640px. No UI library (D7) — the focus trap is hand-rolled with refs:
 * focus moves to the first focusable element on open, Tab/Shift+Tab cycle
 * inside, Escape and backdrop clicks dismiss, and focus returns to the
 * trigger on close. Body scroll is locked while open.
 */
export function Modal({ open, onClose, title, children }: ModalProps) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      const dialog = dialogRef.current;
      if (dialog === null) return;
      const focusable = Array.from(
        dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      );
      if (focusable.length === 0) return;

      const first = focusable[0] as HTMLElement;
      const last = focusable[focusable.length - 1] as HTMLElement;
      const active = document.activeElement;

      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return;

    previouslyFocused.current = document.activeElement as HTMLElement | null;
    // Move focus to the first focusable element inside the dialog.
    const focusFirst = window.setTimeout(() => {
      const first =
        dialogRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
      first?.focus();
    }, 0);

    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown, true);

    return () => {
      window.clearTimeout(focusFirst);
      document.body.style.overflow = "";
      document.removeEventListener("keydown", handleKeyDown, true);
      // Return focus to the trigger.
      previouslyFocused.current?.focus();
    };
  }, [open, handleKeyDown]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-xs"
      onClick={onClose}
      data-testid="modal-backdrop"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        data-testid="modal-dialog"
        className={`${SURFACES.dialog} w-full max-w-md rounded-b-none sm:rounded-2xl sm:max-w-md`}
        onClick={(event) => event.stopPropagation()}
      >
        {/* §6.6's tactile pull-handle bar (mobile bottom sheet). */}
        <div className="sm:hidden w-12 h-1.5 bg-slate-300 dark:bg-slate-600 rounded-full mx-auto mb-4" />
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            type="button"
            aria-label="Close dialog"
            onClick={onClose}
            className="bg-transparent hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 font-medium rounded-lg transition-colors h-8 w-8"
          >
            ×
          </button>
        </div>
        <div>{children}</div>
      </div>
    </div>
  );
}
