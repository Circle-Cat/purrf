import { describe, it, expect } from "vitest";
import {
  POSTINGS_GUIDE,
  POSTING_EDITOR_GUIDE,
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
      expect.arrayContaining([
        "Initial Request",
        "Revision Request",
        "Close Request",
        "Reopen Request",
      ]),
    );
    expect(REVIEWS_GUIDE.steps.length).toBeGreaterThan(0);
  });

  it("POSTING_EDITOR_GUIDE covers the form's key concepts with a custom legend heading", () => {
    expect(POSTING_EDITOR_GUIDE.title).toBeTruthy();
    expect(POSTING_EDITOR_GUIDE.statusesTitle).toBe("Key concepts");
    expect(POSTING_EDITOR_GUIDE.statuses.map((s) => s.name)).toEqual(
      expect.arrayContaining(["Owner(s)", "Stage"]),
    );
    expect(POSTING_EDITOR_GUIDE.steps.length).toBeGreaterThan(0);
  });

  it("every step has a non-empty title and detail", () => {
    for (const guide of [POSTINGS_GUIDE, REVIEWS_GUIDE, POSTING_EDITOR_GUIDE]) {
      for (const step of guide.steps) {
        expect(step.title).toBeTruthy();
        expect(step.detail).toBeTruthy();
      }
    }
  });
});
