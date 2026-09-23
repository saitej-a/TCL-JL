/**
 * Date helpers shared by the 9.3 views. Formatting is done from the ISO
 * parts, never through `toLocaleDateString` — the test suite (and any CI in a
 * non-UTC timezone) must not see a date shift a day at a timezone boundary.
 */

const MONTHS_SHORT = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;

/** "2026-04-23" → "23 Apr 2026" (the spec's §7.4/§7.5 date style). */
export function formatDateShort(isoDate: string): string {
  const [year, month, day] = isoDate.slice(0, 10).split("-");
  const monthIndex = Number(month) - 1;
  const monthName = MONTHS_SHORT[monthIndex] ?? month;
  return `${day} ${monthName} ${year}`;
}

/** Whole days between an ISO date and now (for "waiting since N days"). */
export function daysSince(isoDate: string): number {
  const then = new Date(`${isoDate.slice(0, 10)}T00:00:00Z`).getTime();
  const now = Date.now();
  return Math.max(0, Math.floor((now - then) / 86_400_000));
}

/** Compact relative time ("just now", "2h ago", "5d ago") for feed cards. */
export function timeAgo(isoTimestamp: string): string {
  const seconds = Math.floor((Date.now() - new Date(isoTimestamp).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDateShort(isoTimestamp);
}
