/**
 * The §7.1 landing page: hero, live stats band (04 §80), feature cards, and
 * the §5.6 footer disclaimer. Public read (no guard).
 *
 * Failure honesty: if /public/stats/ fails, the band renders the fallback
 * message — never fabricated numbers (the numbers ARE the product's claim).
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getPublicStats, type PublicStats } from "@/api/stats";
import { Disclaimer } from "@/components/Disclaimer";
import { Skeleton } from "@/components/Skeleton";

const FEATURES = [
  {
    title: "Peer-verified timeline",
    body: "Timeline events are confirmed by candidates in the same batch and region, so the community timeline stays trustworthy.",
  },
  {
    title: "Batch analytics",
    body: "Understand cohort waves and expected dispatch windows from community-reported data — privacy-suppressed below the threshold.",
  },
  {
    title: "Privacy-first identity",
    body: "A pseudonymous display name is all the community ever sees. Your email stays private; anonymity is one toggle away.",
  },
] as const;

const FALLBACK =
  "Live stats are unavailable right now — they will return as soon as the community numbers do.";

export function LandingPage() {
  const [stats, setStats] = useState<PublicStats | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getPublicStats()
      .then((s) => {
        if (!cancelled) setStats(s);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const statCells: Array<[string, number]> | null =
    stats === null
      ? null
      : [
          ["Candidates tracked", stats.registered_candidates],
          ["Community posts", stats.community_posts],
          ["Timeline events", stats.timeline_events],
        ];

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 dark:bg-slate-900" data-testid="landing-page">
      {/* Nav bar (§7.1) */}
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2" aria-label="TCS Joining Tracker home">
            <span className="inline-flex items-center justify-center rounded-lg bg-brand-600 px-2 py-1 text-xs font-bold text-white">
              TJT
            </span>
            <span className="text-base font-bold tracking-tight text-slate-900 dark:text-slate-100">
              TCS Joining Tracker
            </span>
          </Link>
          <div className="flex items-center gap-2">
            <Link
              to="/login"
              className="flex min-h-[44px] items-center rounded-lg border border-slate-200 px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Sign in
            </Link>
            <Link
              to="/register"
              className="flex min-h-[44px] items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700"
            >
              Create account
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4">
        {/* Hero (§7.1, Stitch landing mockup) */}
        <section className="py-14 text-center sm:py-20">
          <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 dark:border-brand-800 dark:bg-brand-950/60 dark:text-brand-300">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            Live community tracker
          </span>
          <h1 className="mx-auto mt-5 max-w-3xl text-3xl font-bold tracking-tight text-slate-900 sm:text-5xl dark:text-slate-50">
            Know where you stand. Without the guesswork.
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-base text-slate-600 dark:text-slate-400">
            A community-built tracker for TCS joining letters: peer-verified timeline events, batch
            analytics, and status updates from candidates like you.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/register"
              className="flex min-h-[44px] items-center rounded-lg bg-brand-600 px-6 text-sm font-medium text-white hover:bg-brand-700"
            >
              Track my joining journey
            </Link>
            <Link
              to="/analytics"
              className="flex min-h-[44px] items-center rounded-lg border border-slate-200 px-6 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Explore community stats
            </Link>
          </div>
          <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
            Free &amp; anonymous · No corporate login required · Pseudonymous by design
          </p>
        </section>

        {/* Live stats band (04 §80) */}
        <section aria-label="Live community stats" className="pb-14">
          <div className="grid gap-4 sm:grid-cols-3">
            {statCells === null && !failed && (
              <>
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
              </>
            )}
            {failed && (
              <p className="sm:col-span-3 text-sm text-slate-500 dark:text-slate-400" role="status">
                {FALLBACK}
              </p>
            )}
            {statCells !== null &&
              statCells.map(([label, value]) => (
                <div
                  key={label}
                  className="rounded-xl border border-slate-200 bg-white p-5 text-center shadow-sm dark:border-slate-800 dark:bg-slate-800"
                >
                  <p className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
                    {value.toLocaleString()}
                  </p>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{label}</p>
                </div>
              ))}
          </div>
          <p className="mt-3 text-center text-[11px] text-slate-500 dark:text-slate-400">
            Community-reported data, not official TCS metrics.
          </p>
        </section>

        {/* Feature cards (§7.1) */}
        <section className="pb-16">
          <h2 className="text-center text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
            Built by candidates, for candidates
          </h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-800"
              >
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{f.title}</p>
                <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                  {f.body}
                </p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 px-4 py-4 dark:border-slate-800">
        <div className="mx-auto max-w-3xl text-center">
          <Disclaimer variant="footer" />
        </div>
      </footer>
    </div>
  );
}
