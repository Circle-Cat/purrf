import { describe, it, expect } from "vitest";
import {
  POSTINGS_GUIDE,
  REVIEWS_GUIDE,
} from "@/pages/Recruiting/components/guideContent";

describe("recruiting guide content", () => {
  it("POSTINGS_GUIDE has a title, steps, statuses, and notes", () => {
    expect(POSTINGS_GUIDE.title).toBeTruthy();
    expect(POSTINGS_GUIDE.steps.length).toBeGreaterThan(0);
    expect(POSTINGS_GUIDE.statuses.map((s) => s.name)).toContain("Published");
    expect(POSTINGS_GUIDE.notes.length).toBeGreaterThan(0);
  });

  it("REVIEWS_GUIDE covers the four review kinds", () => {
    const names = REVIEWS_GUIDE.statuses.map((s) => s.name);
    expect(names).toEqual(
      expect.arrayContaining(["Initial", "Revision", "Close", "Reopen"]),
    );
    expect(REVIEWS_GUIDE.steps.length).toBeGreaterThan(0);
  });

  it("every step has a non-empty title and detail", () => {
    for (const guide of [POSTINGS_GUIDE, REVIEWS_GUIDE]) {
      for (const step of guide.steps) {
        expect(step.title).toBeTruthy();
        expect(step.detail).toBeTruthy();
      }
    }
  });
});
