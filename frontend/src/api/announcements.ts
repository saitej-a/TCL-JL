/**
 * Public announcements (04 §72) — feeds the §5.5 shell banner (D3).
 * Public read shape: {id, title, body, is_pinned, published_at, expires_at};
 * the list endpoint is anonymous-readable and only ever returns published,
 * unexpired rows (server-enforced). NOTE (verification finding): the real
 * route is `/announcements/` — 04 §72's path — not `/community/announcements/`
 * (that URL 404s; the plan's context file guessed the community prefix).
 */
import { apiGet } from "@/api/client";
import type { Paginated } from "@/types/api";

export interface AnnouncementPublic {
  id: string;
  title: string;
  body: string;
  is_pinned: boolean;
  published_at: string | null;
  expires_at: string | null;
}

export function listAnnouncements(): Promise<Paginated<AnnouncementPublic>> {
  return apiGet<Paginated<AnnouncementPublic>>("/announcements/");
}
