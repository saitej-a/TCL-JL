/**
 * Per-announcement dismiss persistence (9.2 D3).
 * Key: `tjt.dismissed_announcements` — a JSON array of announcement ids, so a
 * NEW announcement is never hidden by an old dismissal. Every access is
 * guarded: a browser with storage disabled degrades to "never dismissed".
 */
const KEY = "tjt.dismissed_announcements";

export function readDismissedAnnouncements(): string[] {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (raw === null) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function recordDismissedAnnouncement(id: string): void {
  try {
    const dismissed = readDismissedAnnouncements();
    if (!dismissed.includes(id)) {
      dismissed.push(id);
      window.localStorage.setItem(KEY, JSON.stringify(dismissed));
    }
  } catch {
    // Storage unavailable: the banner may reappear next load. Acceptable.
  }
}
