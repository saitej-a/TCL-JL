/**
 * Public stats (04 §80) — the landing page's KPI counters.
 *
 * Real shipped shape (apps/analytics/services.py get_public_stats): three
 * cross-app counts plus the metadata envelope. The mockup's 4-number band is
 * aspirational; the API ships exactly these three (recorded divergence).
 */
import { apiGet } from "@/api/client";

export interface PublicStats {
  data_source: string;
  disclaimer: string;
  registered_candidates: number;
  community_posts: number;
  timeline_events: number;
}

export function getPublicStats(): Promise<PublicStats> {
  return apiGet<PublicStats>("/public/stats/");
}
