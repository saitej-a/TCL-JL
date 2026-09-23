import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Skeleton, SkeletonCard } from "@/components/Skeleton";
import { useAuth } from "@/context/AuthContext";
import { AppShell } from "@/layouts/AppShell";

/**
 * 05 §3.1's guard as a layout route: unauthenticated visitors go to
 * `/login?next=<path>`. While `booting` (the silent refresh is in flight)
 * render a skeleton — NEVER a redirect, or a page reload would bounce a
 * signed-in user to /login (D1's reload rule, T-09.1-04).
 *
 * 9.2 additions: authenticated children render inside the responsive
 * AppShell, and the 9.2 D1 gate sends users whose `profile_completed` is
 * false to /onboarding (exempting /onboarding itself — T-09.2-01's loop
 * guard). The flag is truthful since the 9.2 backend fix.
 */
export function RequireAuth() {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "booting") {
    return (
      <div className="space-y-4 p-6" aria-busy="true" aria-live="polite">
        <Skeleton className="h-8 w-64" />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (status === "anonymous") {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  // 9.2 D1: the onboarding gate (truthful flag post-backend-fix).
  if (user !== null && !user.profile_completed && location.pathname !== "/onboarding") {
    return <Navigate to="/onboarding" replace />;
  }

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
