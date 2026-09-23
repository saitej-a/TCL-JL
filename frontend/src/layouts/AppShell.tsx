/**
 * The authenticated chrome (UI-01): responsive per §5.2/§5.3/§5.4.
 *
 * - ≥1280px (§5.2's 3-col): sidebar 240px + center + right rail 320px.
 * - 640–1279px (§5.3 tablet): sidebar persists, rail collapses.
 * - <640px (§5.4 mobile): top app bar + fixed bottom tab bar, ≥44px targets.
 *
 * The §5.5 banner renders above the shell at every breakpoint; the §5.6
 * footer disclaimer renders at every breakpoint (the roadmap done-when).
 * Staff navigation is deliberately absent (9.2 D2).
 */
import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";

import { listAnnouncements } from "@/api/announcements";
import { Disclaimer } from "@/components/Disclaimer";
import {
  readDismissedAnnouncements,
  recordDismissedAnnouncement,
} from "@/components/announcementStorage";
import { useAuth } from "@/context/AuthContext";
import { MobileTabBar } from "@/layouts/MobileTabBar";
import { NAV_ITEMS } from "@/layouts/navItems";

const BRAND = (
  <Link
    to="/dashboard"
    aria-label="TCS Joining Tracker home"
    className="flex items-center gap-2 px-3 py-2"
  >
    <span className="inline-flex items-center justify-center rounded-lg bg-brand-600 px-2 py-1 text-xs font-bold text-white">
      TJT
    </span>
    <span className="text-base font-bold tracking-tight text-slate-900 dark:text-slate-100">
      Tracker
    </span>
  </Link>
);

function navLinkClasses({ isActive }: { isActive: boolean }): string {
  return [
    "flex min-h-[44px] items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium",
    isActive
      ? "bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300"
      : "text-slate-600 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800",
  ].join(" ");
}

/** The §5.5 announcement banner (D3): latest un-dismissed announcement, persisted dismissal. */
function AnnouncementBanner() {
  const [item, setItem] = useState<{ id: string; title: string; body: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    listAnnouncements()
      .then((page) => {
        if (cancelled) return;
        const dismissed = readDismissedAnnouncements();
        const showable = page.results.find((a) => !dismissed.includes(a.id));
        setItem(
          showable ? { id: showable.id, title: showable.title, body: showable.body } : null,
        );
      })
      .catch(() => {
        // Chrome, not content: silent degradation on API failure.
        if (!cancelled) setItem(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (item === null) return null;

  return (
    <div
      data-testid="announcement-banner"
      className="flex items-center justify-between gap-3 bg-brand-700 px-4 py-2 text-sm text-white"
    >
      <p className="flex min-w-0 items-center gap-2 truncate">
        <span aria-hidden="true">📣</span>
        <span className="font-semibold">{item.title}</span>
        {item.body !== "" && <span className="hidden truncate font-normal opacity-90 sm:inline">{item.body}</span>}
        <Link to="/notifications" className="whitespace-nowrap underline opacity-90 hover:opacity-100">
          Read update
        </Link>
      </p>
      <button
        type="button"
        aria-label="Dismiss announcement"
        data-testid="dismiss-announcement"
        className="shrink-0 rounded-md px-2 py-1.5 hover:bg-white/10"
        onClick={() => {
          recordDismissedAnnouncement(item.id);
          setItem(null);
        }}
      >
        ×
      </button>
    </div>
  );
}

export function AppShell({ children }: { children?: ReactNode }) {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900" data-testid="app-shell">
      <AnnouncementBanner />
      <div className="lg:grid lg:grid-cols-[240px_minmax(0,1fr)] xl:grid-cols-[240px_minmax(0,1fr)_320px]">
        {/* Sidebar: ≥640px (§5.3 persists it; §5.2 shows it beside the rail) */}
        <aside className="hidden border-slate-200 dark:border-slate-800 lg:sticky lg:top-0 lg:block lg:h-screen lg:border-r">
          <div className="flex h-full flex-col justify-between p-3">
            <div>
              {BRAND}
              <nav aria-label="Primary" className="mt-3 space-y-1">
                {NAV_ITEMS.map((item) => (
                  <NavLink key={item.to} to={item.to} className={navLinkClasses}>
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </div>
            <div className="space-y-1 px-3 pb-4 text-xs text-slate-500 dark:text-slate-400">
              <Link to="/about" className="block py-1 hover:text-slate-800 dark:hover:text-slate-200">
                About
              </Link>
              <Link to="/privacy" className="block py-1 hover:text-slate-800 dark:hover:text-slate-200">
                Privacy
              </Link>
              <Link to="/terms" className="block py-1 hover:text-slate-800 dark:hover:text-slate-200">
                Terms
              </Link>
            </div>
          </div>
        </aside>

        {/* Center column */}
        <div className="flex min-h-screen min-w-0 flex-col">
          <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95">
            {/* Mobile app bar (§5.4) */}
            <div className="flex items-center justify-between px-4 py-2 lg:hidden">
              {BRAND}
              <div className="flex items-center gap-2">
                <Link
                  to="/notifications"
                  aria-label="Notifications"
                  className="flex h-11 w-11 items-center justify-center rounded-full hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  🔔
                </Link>
              </div>
            </div>
            {/* Desktop/tablet search row (§7.4) */}
            <div className="hidden items-center justify-between gap-4 px-6 py-2.5 lg:flex">
              <input
                type="search"
                aria-label="Search community"
                placeholder="Search community…"
                className="w-80 rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800/50"
              />
              <div className="flex items-center gap-3">
                <Link
                  to="/community/create"
                  className="flex min-h-[40px] items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-brand-700"
                >
                  + Post
                </Link>
                {user !== null && (
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-200">
                    {user.email}
                  </span>
                )}
              </div>
            </div>
          </header>

          <main className="flex-1 px-4 pb-24 pt-4 lg:px-8 lg:pb-8">{children ?? <Outlet />}</main>

          <footer className="border-t border-slate-200 px-4 py-3 lg:px-8 dark:border-slate-800">
            <Disclaimer variant="footer" />
          </footer>
        </div>

        {/* Right rail: §5.2's 320px rail at ≥1280px only; 9.3 fills it */}
        <aside className="hidden border-slate-200 dark:border-slate-800 xl:sticky xl:top-0 xl:block xl:h-screen xl:border-l">
          <div className="space-y-4 p-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                My Status Summary
              </p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Placeholder — 9.3 fills this rail.
              </p>
            </div>
          </div>
        </aside>
      </div>

      {/* Mobile bottom tab bar (§5.4) */}
      <MobileTabBar />
    </div>
  );
}
