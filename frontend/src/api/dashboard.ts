/**
 * Dashboard API (04 §28) — the payload `build_dashboard_payload` ships, typed
 * exactly. The analytics block is a **union**: when `suppressed` is true the
 * counts are OMITTED (never zeroed — 4.2 D2), so the type forces callers to
 * handle the message shape before touching a number.
 */
import { apiGet } from "@/api/client";
import type { CandidateStatus } from "@/types/user";

export interface DashboardAnalyticsSuppressed {
  data_source: string;
  suppressed: true;
  message: string;
}

export interface DashboardAnalyticsAvailable {
  data_source: string;
  suppressed: false;
  community_waiting_count: number;
  status_distribution: Record<CandidateStatus, number>;
}

export type DashboardAnalytics =
  | DashboardAnalyticsSuppressed
  | DashboardAnalyticsAvailable;

export interface DashboardPayload {
  profile: {
    completion_percentage: number;
    current_status: CandidateStatus;
  };
  timeline: {
    latest_event: { event_type: string; event_date: string } | null;
  };
  community: {
    unread_notifications: number;
  };
  analytics: DashboardAnalytics;
}

export function getDashboard(): Promise<DashboardPayload> {
  return apiGet<DashboardPayload>("/dashboard/");
}
