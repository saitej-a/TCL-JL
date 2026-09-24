/**
 * CategoryTabs tests (§7.6): the pill row carries exactly the D7 vocabulary
 * plus "All", the three tabs map to the API's tab keys, and selection fires
 * the callbacks.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { CategoryTabs, FEED_TABS } from "@/components/CategoryTabs";
import { POST_CATEGORIES } from "@/content/postCategories";
import { CATEGORY_LABELS } from "@/theme/badges";

function renderTabs(props: Partial<Parameters<typeof CategoryTabs>[0]> = {}) {
  const picks: { category: string | null; tab: string }[] = [];
  render(
    <CategoryTabs
      category={null}
      tab="newest"
      onCategoryChange={(category) => picks.push({ category, tab: "newest" })}
      onTabChange={(tab) => picks.push({ category: null, tab })}
      {...props}
    />,
  );
  return { picks };
}

describe("CategoryTabs", () => {
  it("caps the pill row and reveals the rest through More, per the design", async () => {
    const user = userEvent.setup();
    renderTabs();
    // All + the first five categories + the three tabs — not all twelve pills.
    expect(screen.getAllByRole("radio")).toHaveLength(1 + 5 + FEED_TABS.length);
    expect(screen.getByRole("radio", { name: "All" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Joining Letter" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Offer Letter" })).toBeInTheDocument();
    expect(screen.queryByRole("radio", { name: "Help Needed" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /More/ }));
    // Expanded, the whole D7 vocabulary is reachable and nothing else appears.
    expect(screen.getAllByRole("radio")).toHaveLength(
      POST_CATEGORIES.length + 1 + FEED_TABS.length,
    );
    expect(screen.getByRole("radio", { name: "Help Needed" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Fewer/ })).toBeInTheDocument();
  });

  it("keeps a category chosen from behind the fold on screen", () => {
    const hidden = POST_CATEGORIES[POST_CATEGORIES.length - 1] ?? "OTHER";
    renderTabs({ category: hidden });
    // The active filter is never hidden behind the disclosure it came from.
    expect(
      screen.getByRole("radio", { name: CATEGORY_LABELS[hidden], checked: true }),
    ).toBeInTheDocument();
  });

  it("fires onCategoryChange with the selected key and null for All", async () => {
    const user = userEvent.setup();
    const { picks } = renderTabs();
    await user.click(screen.getByRole("radio", { name: "Joining Letter" }));
    await user.click(screen.getByRole("radio", { name: "All" }));
    expect(picks).toEqual([{ category: "JOINING_LETTER", tab: "newest" }, { category: null, tab: "newest" }]);
  });

  it("carries §7.6's tab labels verbatim", () => {
    renderTabs();
    // The spec writes the sort row as "Latest (Newest First)" /
    // "Trending (Most Active)" / "Top Voted" — the labels are copy, the values
    // are what reach the API.
    expect(FEED_TABS.map((entry) => entry.label)).toEqual([
      "Latest (Newest First)",
      "Trending (Most Active)",
      "Top Voted",
    ]);
    expect(screen.getByRole("radio", { name: "Latest (Newest First)" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Trending (Most Active)" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Top Voted" })).toBeInTheDocument();
  });

  it("switches the sort tab", async () => {
    const user = userEvent.setup();
    const { picks } = renderTabs();
    await user.click(screen.getByRole("radio", { name: "Trending (Most Active)" }));
    expect(picks).toEqual([{ category: null, tab: "trending" }]);
  });
});
