import { Navigate, Outlet } from "react-router-dom";

import { Skeleton, SkeletonCard } from "@/components/Skeleton";
import { useAuth } from "@/context/AuthContext";

/**
 * 05 §3.1 as a layout route: `/login` and `/register` send authenticated
 * users to `/dashboard`. `booting` renders the skeleton for the same reason
 * as RequireAuth — the session is still being restored, so the visitor's
 * eventual destination is not yet known. Anonymous renders the matched child
 * route via <Outlet />.
 */
export function PublicOnly() {
  const { status } = useAuth();

  if (status === "booting") {
    return (
      <div className="p-6 space-y-4" aria-busy="true" aria-live="polite">
        <Skeleton className="h-8 w-64" />
        <SkeletonCard />
      </div>
    );
  }

  if (status === "authenticated") {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
