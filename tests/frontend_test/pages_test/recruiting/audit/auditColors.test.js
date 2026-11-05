import { describe, it, expect } from "vitest";
import {
  STAGE_COLORS,
  categoricalColor,
} from "@/pages/Recruiting/audit/auditColors";

describe("STAGE_COLORS", () => {
  it("has an entry for every application stage", () => {
    expect(Object.keys(STAGE_COLORS).sort()).toEqual(
      [
        "recruiter_screening",
        "behavioral",
        "tech",
        "board_review",
        "offer",
        "hired",
        "rejected",
        "offer_declined",
        "blacklisted",
      ].sort(),
    );
  });

  it("each value is a CSS var() reference, not a raw hex", () => {
    for (const value of Object.values(STAGE_COLORS)) {
      expect(value).toMatch(/^var\(--stage-[a-z-]+\)$/);
    }
  });
});

describe("categoricalColor", () => {
  it("assigns colors by position in the full job list, not the filtered subset", () => {
    const allJobIds = [10, 20, 30, 40];
    // Job 30 is 3rd in the FULL list regardless of which subset is passed for filtering elsewhere.
    expect(categoricalColor(30, allJobIds)).toBe("var(--categorical-3)");
  });

  it("is stable across full-list reordering by sorting ids ascending internally", () => {
    const shuffled = [40, 10, 30, 20];
    expect(categoricalColor(10, shuffled)).toBe("var(--categorical-1)");
    expect(categoricalColor(40, shuffled)).toBe("var(--categorical-4)");
  });

  it("cycles after 8 jobs (never a generated hue for a 9th)", () => {
    const nineJobs = [1, 2, 3, 4, 5, 6, 7, 8, 9];
    expect(categoricalColor(9, nineJobs)).toBe("var(--categorical-1)");
  });
});
