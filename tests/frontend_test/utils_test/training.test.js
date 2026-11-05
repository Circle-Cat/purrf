import { describe, it, expect } from "vitest";

import {
  ONBOARDING_TRAINING_CATEGORIES,
  isIncompleteOnboarding,
} from "@/utils/training";

describe("isIncompleteOnboarding", () => {
  it("is true for a mentor onboarding that is not done", () => {
    expect(
      isIncompleteOnboarding({
        category: "mentorship_mentor_onboarding",
        status: "to_do",
      }),
    ).toBe(true);
  });

  it("is true for a mentee onboarding in progress", () => {
    expect(
      isIncompleteOnboarding({
        category: "mentorship_mentee_onboarding",
        status: "in_progress",
      }),
    ).toBe(true);
  });

  it("is false once the onboarding is done", () => {
    expect(
      isIncompleteOnboarding({
        category: "mentorship_mentee_onboarding",
        status: "done",
      }),
    ).toBe(false);
  });

  it("is false for a non-onboarding category, however incomplete", () => {
    expect(
      isIncompleteOnboarding({
        category: "corporate_culture_course",
        status: "to_do",
      }),
    ).toBe(false);
  });

  it("lists exactly the two mentorship onboarding categories", () => {
    expect(ONBOARDING_TRAINING_CATEGORIES).toEqual([
      "mentorship_mentor_onboarding",
      "mentorship_mentee_onboarding",
    ]);
  });
});
