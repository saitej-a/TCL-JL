import { describe, expect, it } from "vitest";

import {
  CATEGORY_BADGE_CLASSES,
  STATUS_BADGE_CLASSES,
} from "./badges";
import { CANDIDATE_STATUSES, POST_CATEGORIES } from "@/types/user";

describe("CATEGORY_BADGE_CLASSES", () => {
  it("covers exactly the API's 12 POST_CATEGORIES keys", () => {
    expect(Object.keys(CATEGORY_BADGE_CLASSES).sort()).toEqual(
      [...POST_CATEGORIES].sort(),
    );
    expect(POST_CATEGORIES).toHaveLength(12);
  });

  it("maps OFFER_LETTER to the spec's OFFER emerald triple", () => {
    const classes = CATEGORY_BADGE_CLASSES.OFFER_LETTER;
    expect(classes.bg).toContain("bg-emerald-50");
    expect(classes.bg).toContain("dark:bg-emerald-950/50");
    expect(classes.text).toContain("text-emerald-700");
    expect(classes.text).toContain("dark:text-emerald-300");
    expect(classes.border).toContain("border-emerald-200");
  });

  it("uses the GENERAL slate treatment for the two categories the spec omits", () => {
    for (const key of ["LOCATION", "DOCUMENTS"] as const) {
      expect(CATEGORY_BADGE_CLASSES[key].bg).toBe(
        CATEGORY_BADGE_CLASSES.GENERAL.bg,
      );
    }
  });
});

describe("STATUS_BADGE_CLASSES", () => {
  it("covers exactly the 11 CandidateProfile.Status choices", () => {
    expect(Object.keys(STATUS_BADGE_CLASSES).sort()).toEqual(
      [...CANDIDATE_STATUSES].sort(),
    );
    expect(CANDIDATE_STATUSES).toHaveLength(11);
  });

  it("keeps WAITING_FOR_JOINING_LETTER's amber border and animate-pulse", () => {
    const classes = STATUS_BADGE_CLASSES.WAITING_FOR_JOINING_LETTER;
    expect(classes.bg).toContain("bg-amber-100");
    expect(classes.border).toContain("border-amber-300");
    expect(classes.text).toContain("animate-pulse");
  });
});
