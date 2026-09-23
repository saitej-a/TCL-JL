/**
 * The shared auth-card language (§7.2's pattern, per the Stitch auth mockups):
 * centered card, brand row, per-screen heading, error/success strips, and the
 * §5.6 registration disclaimer under the card.
 */
import type { ReactElement, ReactNode } from "react";
import { Link } from "react-router-dom";

import { Disclaimer } from "@/components/Disclaimer";

export function BrandRow() {
  return (
    <Link to="/" className="flex items-center gap-2" aria-label="TCS Joining Tracker home">
      <span className="inline-flex items-center justify-center rounded-lg bg-brand-600 px-2 py-1 text-xs font-bold text-white">
        TJT
      </span>
      <span className="text-base font-bold tracking-tight text-slate-900 dark:text-slate-100">
        TCS Joining Tracker
      </span>
    </Link>
  );
}

/** rose-50 error strip; the message text is the caller's responsibility. */
export function ErrorStrip({ message }: { message: string }) {
  return (
    <p
      role="alert"
      className="flex items-center gap-2 rounded-lg border border-rose-200/60 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300"
    >
      {message}
    </p>
  );
}

/** emerald-50 success strip. */
export function SuccessStrip({ message }: { message: string }) {
  return (
    <p
      role="status"
      className="flex items-center gap-2 rounded-lg border border-emerald-200/80 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300"
    >
      {message}
    </p>
  );
}

interface AuthCardProps {
  title: string;
  subtitle: string;
  children: ReactNode;
  /** Renders below the card instead of the registration disclaimer. */
  footerVariant?: "registration" | "footer";
}

export function AuthCard({ title, subtitle, children, footerVariant = "registration" }: AuthCardProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 py-10 dark:bg-slate-900">
      <div className="w-full max-w-md rounded-2xl border border-slate-100 bg-white p-8 shadow-xl dark:border-slate-800 dark:bg-slate-800">
        <BrandRow />
        <h1 className="mt-6 text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
          {title}
        </h1>
        <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>
        <div className="mt-6 space-y-4">{children}</div>
      </div>
      <div className="mx-auto mt-6 max-w-xl text-center">
        <Disclaimer variant={footerVariant} />
      </div>
    </div>
  );
}

/** Small labeled field wrapper keeping the six screens' markup uniform. */
export function AuthField({
  label,
  htmlFor,
  hint,
  children,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  children: ReactElement;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-200">
        {label}
      </label>
      {children}
      {hint !== undefined && (
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{hint}</p>
      )}
    </div>
  );
}
