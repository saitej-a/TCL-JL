/**
 * Badge color maps (Task 1) — the single typed home for category and status
 * badge styling. Components never re-type these classes; a missing or
 * misspelled key is a compile error because the maps are `Record`-typed over
 * the backend vocabularies.
 */
import type { CandidateStatus, PostCategory } from "@/types/user";

export interface BadgeClasses {
  /** Badge background, light/dark pair. */
  bg: string;
  /** Badge text color, light/dark pair. */
  text: string;
  /** Border accent, light/dark pair (empty when the spec has no border). */
  border: string;
}

/**
 * 05 §4.1.4's matrix, keyed by the API's 12 POST_CATEGORIES.
 *
 * Recorded divergence: the spec's `OFFER` row is the API's `OFFER_LETTER`, and
 * `LOCATION`/`DOCUMENTS` have no spec row — they carry the GENERAL slate
 * treatment as the explicit fallback (see STATE.md Pending Todos).
 */
export const CATEGORY_BADGE_CLASSES: Record<PostCategory, BadgeClasses> = {
  GENERAL: {
    bg: "bg-slate-100 dark:bg-slate-800",
    text: "text-slate-700 dark:text-slate-300",
    border: "border-slate-200 dark:border-slate-700",
  },
  JOINING_LETTER: {
    bg: "bg-indigo-50 dark:bg-indigo-950/50",
    text: "text-indigo-700 dark:text-indigo-300",
    border: "border-indigo-200 dark:border-indigo-800",
  },
  // The spec's `OFFER` row (emerald triple) — the API spells it OFFER_LETTER.
  OFFER_LETTER: {
    bg: "bg-emerald-50 dark:bg-emerald-950/50",
    text: "text-emerald-700 dark:text-emerald-300",
    border: "border-emerald-200 dark:border-emerald-800",
  },
  JOINING_DATE: {
    bg: "bg-sky-50 dark:bg-sky-950/50",
    text: "text-sky-700 dark:text-sky-300",
    border: "border-sky-200 dark:border-sky-800",
  },
  // No §4.1.4 row — GENERAL slate treatment as the recorded fallback.
  LOCATION: {
    bg: "bg-slate-100 dark:bg-slate-800",
    text: "text-slate-700 dark:text-slate-300",
    border: "border-slate-200 dark:border-slate-700",
  },
  INTERVIEW: {
    bg: "bg-purple-50 dark:bg-purple-950/50",
    text: "text-purple-700 dark:text-purple-300",
    border: "border-purple-200 dark:border-purple-800",
  },
  // No §4.1.4 row — GENERAL slate treatment as the recorded fallback.
  DOCUMENTS: {
    bg: "bg-slate-100 dark:bg-slate-800",
    text: "text-slate-700 dark:text-slate-300",
    border: "border-slate-200 dark:border-slate-700",
  },
  DISCUSSION: {
    bg: "bg-blue-50 dark:bg-blue-950/50",
    text: "text-blue-700 dark:text-blue-300",
    border: "border-blue-200 dark:border-blue-800",
  },
  TCS_PROCESS: {
    bg: "bg-amber-50 dark:bg-amber-950/50",
    text: "text-amber-700 dark:text-amber-300",
    border: "border-amber-200 dark:border-amber-800",
  },
  HELP: {
    bg: "bg-rose-50 dark:bg-rose-950/50",
    text: "text-rose-700 dark:text-rose-300",
    border: "border-rose-200 dark:border-rose-800",
  },
  ANNOUNCEMENT: {
    bg: "bg-teal-50 dark:bg-teal-950/50",
    text: "text-teal-700 dark:text-teal-300",
    border: "border-teal-200 dark:border-teal-800",
  },
  OTHER: {
    bg: "bg-zinc-100 dark:bg-zinc-800",
    text: "text-zinc-700 dark:text-zinc-300",
    border: "border-zinc-200 dark:border-zinc-700",
  },
};

/**
 * 05 §6.3.1's eleven status badges, keyed by CandidateProfile.Status.
 * WAITING_FOR_JOINING_LETTER keeps its amber border + animate-pulse.
 */
export const STATUS_BADGE_CLASSES: Record<CandidateStatus, BadgeClasses> = {
  REGISTERED: {
    bg: "bg-slate-100 dark:bg-slate-800",
    text: "text-slate-700 dark:text-slate-300",
    border: "",
  },
  INTERVIEWED: {
    bg: "bg-purple-100 dark:bg-purple-950/60",
    text: "text-purple-700 dark:text-purple-300",
    border: "",
  },
  SELECTED: {
    bg: "bg-blue-100 dark:bg-blue-950/60",
    text: "text-blue-700 dark:text-blue-300",
    border: "",
  },
  OFFER_RECEIVED: {
    bg: "bg-teal-100 dark:bg-teal-950/60",
    text: "text-teal-700 dark:text-teal-300",
    border: "",
  },
  READINESS_SURVEY: {
    bg: "bg-amber-100 dark:bg-amber-950/60",
    text: "text-amber-800 dark:text-amber-300",
    border: "",
  },
  // The spec gives this row a light-mode-only styling; the border + pulse are
  // its identity. A dark pair is supplied from the amber surface family.
  WAITING_FOR_JOINING_LETTER: {
    bg: "bg-amber-100 dark:bg-amber-950/60",
    text: "text-amber-900 dark:text-amber-300 animate-pulse",
    border: "border border-amber-300 dark:border-amber-600 animate-pulse",
  },
  JOINING_LETTER_RECEIVED: {
    bg: "bg-indigo-100 dark:bg-indigo-950/60",
    text: "text-indigo-700 dark:text-indigo-300",
    border: "",
  },
  JOINING_DATE_RECEIVED: {
    bg: "bg-sky-100 dark:bg-sky-950/60",
    text: "text-sky-700 dark:text-sky-300",
    border: "",
  },
  JOINED: {
    bg: "bg-emerald-100 dark:bg-emerald-950/60",
    text: "text-emerald-700 dark:text-emerald-300",
    border: "",
  },
  WITHDRAWN: {
    bg: "bg-rose-100 dark:bg-rose-950/60",
    text: "text-rose-700 dark:text-rose-300",
    border: "",
  },
  OTHER: {
    bg: "bg-zinc-100 dark:bg-zinc-800",
    text: "text-zinc-700 dark:text-zinc-300",
    border: "",
  },
};

/** §4.1.4's human labels (spec's `OFFER` row shown under the API's key). */
export const CATEGORY_LABELS: Record<PostCategory, string> = {
  GENERAL: "General",
  JOINING_LETTER: "Joining Letter",
  OFFER_LETTER: "Offer Letter",
  JOINING_DATE: "Joining Date",
  LOCATION: "Location",
  INTERVIEW: "Interview",
  DOCUMENTS: "Documents",
  DISCUSSION: "Discussion",
  TCS_PROCESS: "TCS Process",
  HELP: "Help Needed",
  ANNOUNCEMENT: "Announcement",
  OTHER: "Other",
};

/** §6.3.1's display labels. */
export const STATUS_LABELS: Record<CandidateStatus, string> = {
  REGISTERED: "Registered",
  INTERVIEWED: "Interviewed",
  SELECTED: "Selected",
  OFFER_RECEIVED: "Offer Received",
  READINESS_SURVEY: "Survey Completed",
  WAITING_FOR_JOINING_LETTER: "Waiting for JL",
  JOINING_LETTER_RECEIVED: "JL Received",
  JOINING_DATE_RECEIVED: "Joining Date Set",
  JOINED: "Joined TCS",
  WITHDRAWN: "Withdrawn",
  OTHER: "Other",
};
