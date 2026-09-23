/**
 * The non-CSS half of the token system (Task 1): the 05 §4.3 typography scale
 * and shared structural classes as exported constants, so views never invent
 * values. The color tokens themselves live in `src/index.css` (`@theme`).
 */

/** §4.3 typographic roles, as the spec's own Tailwind classes. */
export const TYPOGRAPHY = {
  displayHero: "text-4xl font-bold tracking-tight",
  pageTitle: "text-2xl sm:text-3xl font-bold tracking-tight",
  sectionHeader: "text-xl sm:text-2xl font-semibold tracking-tight",
  cardTitle: "text-lg font-semibold tracking-tight",
  subheadLabel: "text-sm font-medium",
  bodyPrimary: "text-[15px] leading-relaxed",
  bodySecondary: "text-sm leading-normal",
  caption: "text-xs text-muted",
  badgePill: "text-[11px] font-medium tracking-wide",
  legal: "text-[11px] leading-normal",
} as const;

/** Structural classes the spec fixes once (§6.4, §6.6, §6.7.2). */
export const SURFACES = {
  /** §6.4 card container. */
  card: "bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4 sm:p-5 shadow-sm hover:border-slate-300 dark:hover:border-slate-600 transition-all",
  /** §6.6 desktop dialog. */
  dialog: "bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6 border border-slate-200 dark:border-slate-700",
  /** §6.7.2 skeleton block (base classes, size/shape applied by the caller). */
  skeleton: "animate-pulse bg-slate-200 dark:bg-slate-700",
} as const;

/** Breakpoint at which modals switch to bottom-sheet presentation (§6.6). */
export const BOTTOM_SHEET_MAX_WIDTH_PX = 639;

/** Shared button heights (§6.1.2) so other components align. */
export const BUTTON_HEIGHTS = {
  sm: "h-8",
  md: "h-10",
  lg: "h-12",
} as const;
