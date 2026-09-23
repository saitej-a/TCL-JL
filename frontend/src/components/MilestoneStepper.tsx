/**
 * The §7.4 "recruitment progression" stepper: six milestone nodes driven by
 * the candidate's real timeline events (GET /timeline/ rows — no invented
 * dates, ever). A node completes when an event of its type exists; the final
 * node accepts JOINING_DATE **or** JOINED; OTHER is never a milestone.
 *
 * Desktop renders the horizontal chain with connector strokes; mobile renders
 * the same sequence as a compact scrollable row (§5.4).
 */
import type { TimelineEventType, TimelineEventPrivate } from "@/api/timeline";
import { formatDateShort } from "@/utils/date";

interface MilestoneDef {
  type: TimelineEventType;
  /** Any alternate event type that also satisfies the node. */
  alt?: TimelineEventType;
  label: string;
}

const MILESTONES: readonly MilestoneDef[] = [
  { type: "INTERVIEW", label: "Interview" },
  { type: "SELECTION", label: "Selection" },
  { type: "OFFER_LETTER", label: "Offer" },
  { type: "READINESS_SURVEY", label: "Survey" },
  { type: "JOINING_LETTER", label: "JL" },
  { type: "JOINING_DATE", alt: "JOINED", label: "Join" },
] as const;

export interface MilestoneStepperProps {
  events: TimelineEventPrivate[];
}

/** Earliest date per event type — the node shows when it first happened. */
function completionDates(events: TimelineEventPrivate[]): Map<TimelineEventType, string> {
  const dates = new Map<TimelineEventType, string>();
  for (const event of events) {
    const existing = dates.get(event.event_type);
    if (existing === undefined || event.event_date < existing) {
      dates.set(event.event_type, event.event_date);
    }
  }
  return dates;
}

const DONE_NODE_CLASSES =
  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300";
const PENDING_NODE_CLASSES =
  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-100 text-amber-700 animate-pulse dark:bg-amber-950/60 dark:text-amber-300";
const CONNECTOR_CLASSES = "h-px flex-1 bg-slate-300 dark:bg-slate-600";

export function MilestoneStepper({ events }: MilestoneStepperProps): React.ReactElement {
  const dates = completionDates(events);

  return (
    <ol
      aria-label="Recruitment progression"
      className="flex items-center gap-2 overflow-x-auto pb-1 sm:gap-3"
    >
      {MILESTONES.map((milestone, index) => {
        const date = dates.get(milestone.type) ?? (milestone.alt !== undefined ? dates.get(milestone.alt) : undefined);
        const done = date !== undefined;
        const last = index === MILESTONES.length - 1;
        return (
          <li key={milestone.type} className="flex items-center gap-2 sm:gap-3">
            <div className="flex flex-col items-center gap-1">
              <span className={done ? DONE_NODE_CLASSES : PENDING_NODE_CLASSES} aria-hidden="true">
                {done ? "✓" : "⏳"}
              </span>
              <span
                className={[
                  "whitespace-nowrap text-[11px] font-medium",
                  done
                    ? "text-slate-900 dark:text-slate-100"
                    : "text-slate-500 dark:text-slate-400",
                ].join(" ")}
              >
                {milestone.label}
              </span>
              <span className="whitespace-nowrap text-[11px] text-slate-500 dark:text-slate-400">
                {done ? formatDateShort(date) : "Pending"}
              </span>
            </div>
            {!last && <span className={CONNECTOR_CLASSES} aria-hidden="true" />}
          </li>
        );
      })}
    </ol>
  );
}
