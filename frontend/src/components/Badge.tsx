import {
  CATEGORY_BADGE_CLASSES,
  CATEGORY_LABELS,
  STATUS_BADGE_CLASSES,
  STATUS_LABELS,
  type BadgeClasses,
} from "@/theme/badges";
import type { CandidateStatus, PostCategory } from "@/types/user";

/** §4.3's badge/pill tag classes, shared by both entry points. */
const PILL_CLASSES = "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium tracking-wide";

function classesFor(badge: BadgeClasses): string {
  return [PILL_CLASSES, badge.bg, badge.text, badge.border].filter(Boolean).join(" ");
}

export interface BadgeCategoryProps {
  code: PostCategory;
  className?: string;
}

export interface BadgeStatusProps {
  value: CandidateStatus;
  className?: string;
}

function BaseBadge({ classes, label, className }: { classes: BadgeClasses; label: string; className?: string }) {
  return (
    <span className={`${classesFor(classes)} ${className ?? ""}`.trim()}>
      {label}
    </span>
  );
}

/**
 * Category badge over CATEGORY_BADGE_CLASSES (all 12 API keys). An unknown
 * code never throws — it renders the GENERAL slate fallback (defensive only;
 * the type system already makes a wrong key a compile error for callers).
 */
function CategoryBadge({ code, className }: BadgeCategoryProps) {
  const classes = CATEGORY_BADGE_CLASSES[code] ?? CATEGORY_BADGE_CLASSES.GENERAL;
  return <BaseBadge classes={classes} label={CATEGORY_LABELS[code] ?? code} className={className} />;
}

/**
 * Status badge over STATUS_BADGE_CLASSES (all 11 choices), including
 * WAITING_FOR_JOINING_LETTER's animate-pulse amber treatment.
 */
function StatusBadge({ value, className }: BadgeStatusProps) {
  const classes = STATUS_BADGE_CLASSES[value] ?? STATUS_BADGE_CLASSES.OTHER;
  return <BaseBadge classes={classes} label={STATUS_LABELS[value] ?? value} className={className} />;
}

export const Badge = {
  category: CategoryBadge,
  status: StatusBadge,
};
