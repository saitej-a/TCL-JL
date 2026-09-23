/**
 * Timeline API (04 §24–§25) — the wizard's step-2 write path.
 *
 * Why the event, not PATCH /profile/{current_status}: the PATCH side-channel
 * permits only single-hop transitions (live proof: REGISTERED → OFFER_RECEIVED
 * is rejected), while creating a timeline event walks the chain hop-by-hop
 * (4.1 D1, multi-hop backfills OK) AND records the milestone itself — the
 * product's core data. Event types map to statuses 1:1 (EVENT_TYPE_TO_STATUS);
 * OTHER/WITHDRAWN carry no event semantics and stay PATCH-only.
 */
import { apiGet, apiPost } from "@/api/client";
import type { Paginated } from "@/types/api";

/** The 04 §24.1 event vocabulary (apps/timeline/models.py EventType). */
export type TimelineEventType =
  | "INTERVIEW"
  | "SELECTION"
  | "OFFER_LETTER"
  | "READINESS_SURVEY"
  | "JOINING_LETTER"
  | "JOINING_DATE"
  | "JOINED"
  | "OTHER";

export interface TimelineEventPrivate {
  id: string;
  event_type: TimelineEventType;
  event_date: string;
  description: string;
  is_verified: boolean;
  created_at: string;
}

export interface TimelineEventCreatePayload {
  event_type: TimelineEventType;
  event_date: string;
  description?: string;
}

export function createTimelineEvent(
  payload: TimelineEventCreatePayload,
): Promise<TimelineEventPrivate> {
  return apiPost<TimelineEventPrivate>("/timeline/", payload);
}

export function listMyTimelineEvents(): Promise<Paginated<TimelineEventPrivate>> {
  return apiGet<Paginated<TimelineEventPrivate>>("/timeline/");
}
