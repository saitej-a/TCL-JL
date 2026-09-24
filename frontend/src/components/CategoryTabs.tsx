/**
 * §7.6's filter row, to the design's anatomy: the pill row (`All` plus a capped
 * set of categories with a `+ More` toggle that reveals the rest) and the three
 * sort tabs as a **segmented control** — a track with the active tab raised on
 * its own surface — rather than the underlined text row the first pass shipped.
 *
 * The pill row is a radiogroup so keyboard users get roving focus for free; the
 * `More` toggle is a disclosure button (aria-expanded), never a category.
 *
 * Recorded divergences from the mockup: the design's pills carry counts
 * (`Joining Letter (55)`) and its row shows a `[More]` pill after five
 * categories. Counts have no endpoint (9.3 D7 keeps `GET /posts/categories/`
 * unbuilt), so no number is rendered — but the cap-and-expand behaviour is real,
 * and a category selected from behind the fold stays visible so the active
 * filter is never hidden.
 */
import { useState } from "react";

import { POST_CATEGORIES } from "@/content/postCategories";
import { CATEGORY_LABELS } from "@/theme/badges";

export type FeedTab = "newest" | "trending" | "votes";

export const FEED_TABS: readonly { value: FeedTab; label: string }[] = [
  { value: "newest", label: "Latest (Newest First)" },
  { value: "trending", label: "Trending (Most Active)" },
  { value: "votes", label: "Top Voted" },
] as const;

export interface CategoryTabsProps {
  category: string | null;
  tab: FeedTab;
  onCategoryChange: (category: string | null) => void;
  onTabChange: (tab: FeedTab) => void;
}

/** How many category pills sit above the fold, per the design's row. */
const VISIBLE_CATEGORY_COUNT = 5;

const PILL_ACTIVE =
  "inline-flex min-h-[36px] items-center rounded-full bg-brand-600 px-3 text-xs font-semibold text-white";
const PILL_IDLE =
  "inline-flex min-h-[36px] items-center rounded-full border border-slate-300 px-3 text-xs font-medium text-slate-600 hover:border-brand-300 hover:text-brand-600 dark:border-slate-600 dark:text-slate-300";

const SEGMENT_TRACK =
  "inline-flex flex-wrap gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800";
const SEGMENT_ACTIVE =
  "inline-flex min-h-[34px] items-center gap-1.5 rounded-md bg-white px-3 text-sm font-semibold text-slate-900 shadow-sm dark:bg-slate-700 dark:text-slate-100";
const SEGMENT_IDLE =
  "inline-flex min-h-[34px] items-center rounded-md px-3 text-sm font-medium text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200";

export function CategoryTabs({ category, tab, onCategoryChange, onTabChange }: CategoryTabsProps): React.ReactElement {
  const [expanded, setExpanded] = useState(false);

  const folded = POST_CATEGORIES.slice(0, VISIBLE_CATEGORY_COUNT);
  const rest = POST_CATEGORIES.slice(VISIBLE_CATEGORY_COUNT);
  // The URL carries a bare string; resolve it against the vocabulary so the
  // rest of the component works in PostCategory, not "any string".
  const selected = POST_CATEGORIES.find((key) => key === category) ?? null;
  // A selection made from behind the fold stays on screen.
  const visible = expanded || (selected !== null && !folded.includes(selected)) ? POST_CATEGORIES : folded;

  return (
    <div className="space-y-3">
      <div role="radiogroup" aria-label="Filter by category" className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          role="radio"
          aria-checked={category === null}
          onClick={() => onCategoryChange(null)}
          className={category === null ? PILL_ACTIVE : PILL_IDLE}
        >
          All
        </button>
        {visible.map((key) => (
          <button
            key={key}
            type="button"
            role="radio"
            aria-checked={category === key}
            onClick={() => onCategoryChange(key)}
            className={category === key ? PILL_ACTIVE : PILL_IDLE}
          >
            {CATEGORY_LABELS[key]}
          </button>
        ))}
        {rest.length > 0 && (
          <button
            type="button"
            aria-expanded={expanded}
            onClick={() => setExpanded((current) => !current)}
            className="inline-flex min-h-[36px] items-center rounded-full px-3 text-xs font-medium text-slate-500 underline decoration-dotted hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
          >
            {expanded ? "Fewer" : "+ More"}
          </button>
        )}
      </div>

      <div role="radiogroup" aria-label="Sort posts" className={SEGMENT_TRACK}>
        {FEED_TABS.map((entry) => (
          <button
            key={entry.value}
            type="button"
            role="radio"
            aria-checked={tab === entry.value}
            onClick={() => onTabChange(entry.value)}
            className={tab === entry.value ? SEGMENT_ACTIVE : SEGMENT_IDLE}
          >
            {tab === entry.value && (
              <span className="text-[8px] leading-none text-brand-600 dark:text-brand-400" aria-hidden="true">
                ●
              </span>
            )}
            {entry.label}
          </button>
        ))}
      </div>
    </div>
  );
}
