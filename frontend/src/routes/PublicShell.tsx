import { Outlet } from "react-router-dom";

import { AppShell } from "@/layouts/AppShell";

/**
 * The app frame for public reads (9.3 reconciliation).
 *
 * 05 §3.1 routes `/community` to every role — including visitors — and §7.6's
 * design puts that page **inside** the app frame (240px sidebar, top bar with
 * search, 320px rail, disclaimer footer), not in a bare column. Task 8 read
 * "keep /community public" as access control and implemented it as *no chrome*,
 * which is why the feed rendered as a floating list while every 9.3 mockup
 * showed it framed.
 *
 * Access control is unchanged: the API owns it (D1's anonymous read), and this
 * route adds layout only. `AppShell` already degrades for a signed-out reader —
 * it hides the account email, and the sidebar/top-bar links that need an
 * account send the visitor through `/login?next=<path>` the same way any deep
 * link does.
 */
export function PublicShell() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
