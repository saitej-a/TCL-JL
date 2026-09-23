/**
 * The §5.4 mobile bottom tab bar: five tabs, ≥44px touch targets, active tab
 * in brand indigo. Rendered by AppShell below lg; hidden on desktop.
 */
import { NavLink } from "react-router-dom";

import { MOBILE_TABS } from "@/layouts/navItems";

export function MobileTabBar() {
  return (
    <nav
      aria-label="Primary mobile"
      data-testid="mobile-tab-bar"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] dark:border-slate-800 dark:bg-slate-900 lg:hidden"
    >
      <ul className="grid grid-cols-5">
        {MOBILE_TABS.map((tab) => (
          <li key={tab.to}>
            <NavLink
              to={tab.to}
              className={({ isActive }) =>
                [
                  "flex min-h-[56px] min-w-[44px] flex-col items-center justify-center gap-0.5 py-1 text-[11px] font-medium",
                  isActive
                    ? "text-brand-600 dark:text-brand-400"
                    : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200",
                ].join(" ")
              }
            >
              {tab.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
