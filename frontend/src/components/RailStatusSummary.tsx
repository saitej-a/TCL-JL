/**
 * §7.4's "My Status Summary" rail card, shared by /dashboard (which already has
 * the payload) and /community (whose design fills the same rail).
 *
 * It takes plain values rather than a payload so the two callers can feed it
 * from the endpoint each of them actually reads. Every field is nullable and
 * renders the §6.7.2 skeleton while absent — the card never invents a status.
 */
import { Badge } from "@/components/Badge";
import { Skeleton } from "@/components/Skeleton";
import type { CandidateStatus } from "@/types/user";

export interface RailStatusSummaryProps {
  /** null while the dashboard payload is still loading. */
  status: CandidateStatus | null;
  completion: number | null;
  unread: number | null;
}

export function RailStatusSummary({
  status,
  completion,
  unread,
}: RailStatusSummaryProps): React.ReactElement {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">My Status Summary</p>
      {status === null ? (
        <Skeleton className="mt-2 h-4 w-32" />
      ) : (
        <>
          <div className="mt-2">
            <Badge.status value={status} />
          </div>
          {completion !== null && (
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              Profile {completion}% complete
            </p>
          )}
          {unread !== null && (
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {unread} unread notification{unread === 1 ? "" : "s"}
            </p>
          )}
        </>
      )}
    </div>
  );
}
