import { describe, expect, it } from "vitest";

import { POST_CATEGORIES } from "./postCategories";
import { CATEGORY_LABELS } from "@/theme/badges";

describe("POST_CATEGORIES (9.3 D7's single vocabulary module)", () => {
  it("holds exactly the backend's 12 keys, in backend order", () => {
    expect([...POST_CATEGORIES]).toEqual([
      "GENERAL",
      "JOINING_LETTER",
      "OFFER_LETTER",
      "JOINING_DATE",
      "LOCATION",
      "INTERVIEW",
      "DOCUMENTS",
      "DISCUSSION",
      "TCS_PROCESS",
      "HELP",
      "ANNOUNCEMENT",
      "OTHER",
    ]);
  });

  it("has a UI label for every key (badges.ts stays exhaustive)", () => {
    for (const key of POST_CATEGORIES) {
      expect(CATEGORY_LABELS[key]).toBeTruthy();
    }
  });
});
