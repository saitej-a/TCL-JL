/**
 * The §7.5 vertical roadmap: the candidate's definitive personal record.
 * Real events render newest-first (the server's ordering) with a continuous
 * connector stroke, per-node Edit/Delete on the candidate's own events, and
 * pending milestone slots below with §7.5's quick actions ("Mark as
 * Received" on the joining letter, "Set Date" on the joining date) that open
 * the modal pre-filled with today's date.
 */
import type { TimelineEventType, TimelineEventPrivate } from "@/api/timeline";
import { EVENT_TYPE_OPTIONS } from "@/components/TimelineEventModal";
import { formatDateShort } from "@/utils/date";

interface MilestoneSlot {
  type: TimelineEventType;
  label: string;
  /** Label of §7.5's quick action; null renders no button. */
  quickAction: string | null;
}

/** §7.5's pending slots, in canonical ladder order (OTHER is never a slot). */
const MILESTONE_SLOTS: readonly MilestoneSlot[] = [
  { type: "INTERVIEW", label: "Technical & HR Interview", quickAction: null },
  { type: "SELECTION", label: "Selection Communicated", quickAction: null },
  { type: "OFFER_LETTER", label: "Offer Letter Issued", quickAction: null },
  { type: "READINESS_SURVEY", label: "Joining Readiness Survey Submitted", quickAction: null },
  { type: "JOINING_LETTER", label: "Joining Letter", quickAction: "Mark as Received" },
  { type: "JOINING_DATE", label: "Joining Date & Onboarding", quickAction: "Set Date" },
] as const;

export interface TimelineRoadmapProps {
  events: TimelineEventPrivate[];
  onEdit: (event: TimelineEventPrivate) => void;
  onDelete: (event: TimelineEventPrivate) => void;
  /** Quick action on a milestone slot with no real event yet. */
  onQuickAction: (type: TimelineEventType) => void;
}

const ACTION_BUTTON_CLASSES =
  "min-h-[36px] rounded-lg border px-3 text-xs font-medium transition-colors";

export function TimelineRoadmap({
  events,
  onEdit,
  onDelete,
  onQuickAction,
}: TimelineRoadmapProps): React.ReactElement {
  const recorded = new Set(events.map((event) => event.event_type));
  const pendingSlots = MILESTONE_SLOTS.filter((slot) => !recorded.has(slot.type));

  return (
    <ol className="relative">
      {events.map((event, index) => {
        const last = index === events.length - 1 && pendingSlots.length === 0;
        return (
          <li key={event.id} className="relative flex gap-4 pb-6">
            {!last && (
              <span
                className="absolute left-[13px] top-8 h-[calc(100%-2rem)] w-px bg-slate-300 dark:bg-slate-600"
                aria-hidden="true"
              />
            )}
            <span
              className={[
                "z-10 mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold",
                event.is_verified
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                  : "animate-pulse bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300",
              ].join(" ")}
              aria-hidden="true"
            >
              {event.is_verified ? "✓" : "!"}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                  {formatDateShort(event.event_date)}
                </span>
                <span className="text-sm text-slate-600 dark:text-slate-300">
                  {EVENT_TYPE_OPTIONS.find((option) => option.value === event.event_type)?.label ??
                    event.event_type}
                </span>
                {!event.is_verified && (
                  <span className="text-[11px] font-medium text-amber-700 dark:text-amber-300">
                    unverified
                  </span>
                )}
              </div>
              {event.description !== "" && (
                <p className="mt-1 whitespace-pre-line text-sm text-slate-500 dark:text-slate-400">
                  {event.description}
                </p>
              )}
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  onClick={() => onEdit(event)}
                  className={`${ACTION_BUTTON_CLASSES} border-slate-300 text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800`}
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => onDelete(event)}
                  className={`${ACTION_BUTTON_CLASSES} border-rose-300 text-rose-700 hover:bg-rose-50 dark:border-rose-800 dark:text-rose-300 dark:hover:bg-rose-950/40`}
                >
                  Delete
                </button>
              </div>
            </div>
          </li>
        );
      })}

      {pendingSlots.map((slot, index) => {
        const last = index === pendingSlots.length - 1;
        return (
          <li key={slot.type} className="relative flex gap-4 pb-6 last:pb-0">
            {!last && (
              <span
                className="absolute left-[13px] top-8 h-[calc(100%-2rem)] w-px bg-slate-300 dark:bg-slate-600"
                aria-hidden="true"
              />
            )}
            <span
              className="z-10 mt-0.5 flex h-7 w-7 shrink-0 animate-pulse items-center justify-center rounded-full bg-amber-100 text-xs font-bold text-amber-700 dark:bg-amber-950/60 dark:text-amber-300"
              aria-hidden="true"
            >
              ⏳
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                Pending — {slot.label}
              </p>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                Waiting for this milestone.
              </p>
              {slot.quickAction !== null && (
                <button
                  type="button"
                  onClick={() => onQuickAction(slot.type)}
                  className={`${ACTION_BUTTON_CLASSES} mt-2 border-brand-300 bg-brand-50 text-brand-700 hover:bg-brand-100 dark:border-brand-800 dark:bg-brand-950/40 dark:text-brand-300`}
                >
                  {slot.quickAction}
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
