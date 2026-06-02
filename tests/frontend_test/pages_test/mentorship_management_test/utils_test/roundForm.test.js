import { describe, it, expect } from "vitest";
import {
  validateForm,
  EMPTY_FORM,
} from "@/pages/MentorshipManagement/utils/roundForm";

const BASE_FORM = {
  ...EMPTY_FORM,
  name: "Mentorship 2026 Spring",
  requiredMeetings: 5,
  promotionStartAt: new Date(2025, 11, 18),
  mentorApplicationDeadlineAt: new Date(2025, 11, 25),
  menteeApplicationDeadlineAt: new Date(2025, 11, 25),
  matchNotificationAt: new Date(2026, 1, 12),
  meetingsCompletionDeadlineAt: new Date(2026, 3, 30),
};

describe("validateForm", () => {
  it("returns no errors for a valid form", () => {
    expect(validateForm(BASE_FORM)).toEqual({});
  });

  it("requires name", () => {
    const errors = validateForm({ ...BASE_FORM, name: "  " });
    expect(errors.name).toBe("This field is required.");
  });

  it.each([
    "promotionStartAt",
    "mentorApplicationDeadlineAt",
    "menteeApplicationDeadlineAt",
    "matchNotificationAt",
    "meetingsCompletionDeadlineAt",
  ])("requires %s", (field) => {
    expect(validateForm({ ...BASE_FORM, [field]: null })[field]).toBe(
      "This field is required.",
    );
  });

  it("rejects requiredMeetings outside 0 to 10", () => {
    expect(
      validateForm({ ...BASE_FORM, requiredMeetings: -1 }).requiredMeetings,
    ).toBeTruthy();
    expect(
      validateForm({ ...BASE_FORM, requiredMeetings: 11 }).requiredMeetings,
    ).toBeTruthy();
    expect(
      validateForm({ ...BASE_FORM, requiredMeetings: 0 }).requiredMeetings,
    ).toBeUndefined();
    expect(
      validateForm({ ...BASE_FORM, requiredMeetings: 10 }).requiredMeetings,
    ).toBeUndefined();
  });

  it("requires requiredMeetings to be non-null", () => {
    expect(
      validateForm({ ...BASE_FORM, requiredMeetings: null }).requiredMeetings,
    ).toBe("This field is required.");
  });

  it("rejects mentorApplicationDeadlineAt before promotionStartAt", () => {
    const errors = validateForm({
      ...BASE_FORM,
      promotionStartAt: new Date(2025, 11, 25),
      mentorApplicationDeadlineAt: new Date(2025, 11, 18),
    });
    expect(errors.mentorApplicationDeadlineAt).toMatch(/Sign-up Admin Action/);
  });

  it("rejects menteeApplicationDeadlineAt before promotionStartAt", () => {
    const errors = validateForm({
      ...BASE_FORM,
      promotionStartAt: new Date(2025, 11, 25),
      mentorApplicationDeadlineAt: new Date(2025, 11, 26),
      menteeApplicationDeadlineAt: new Date(2025, 11, 18),
    });
    expect(errors.menteeApplicationDeadlineAt).toMatch(/Sign-up Admin Action/);
  });

  it("allows menteeApplicationDeadlineAt before mentorApplicationDeadlineAt (parallel fields)", () => {
    const errors = validateForm({
      ...BASE_FORM,
      mentorApplicationDeadlineAt: new Date(2025, 11, 30),
      menteeApplicationDeadlineAt: new Date(2025, 11, 26),
    });
    expect(errors.menteeApplicationDeadlineAt).toBeUndefined();
  });

  it("allows mentorApplicationDeadlineAt before menteeApplicationDeadlineAt (parallel fields)", () => {
    const errors = validateForm({
      ...BASE_FORM,
      mentorApplicationDeadlineAt: new Date(2025, 11, 26),
      menteeApplicationDeadlineAt: new Date(2025, 11, 30),
    });
    expect(errors.mentorApplicationDeadlineAt).toBeUndefined();
  });

  it.each([
    {
      mentorApplicationDeadlineAt: new Date(2026, 0, 20),
      menteeApplicationDeadlineAt: new Date(2026, 0, 10),
    },
    {
      mentorApplicationDeadlineAt: new Date(2026, 0, 10),
      menteeApplicationDeadlineAt: new Date(2026, 0, 20),
    },
  ])(
    "uses the latest sign-up deadline as the lower bound for training",
    (overrides) => {
      const invalid = validateForm({
        ...BASE_FORM,
        ...overrides,
        trainingNotificationAt: new Date(2026, 0, 15),
      });
      expect(invalid.trainingNotificationAt).toBeDefined();

      const valid = validateForm({
        ...BASE_FORM,
        ...overrides,
        trainingNotificationAt: new Date(2026, 0, 21),
      });
      expect(valid).toEqual({}); // Training notification is valid once it exceeds the high watermark.
    },
  );

  it("rejects trainingDeadlineAt before its effective ancestor when trainingNotificationAt is empty", () => {
    const errors = validateForm({
      ...BASE_FORM,
      trainingNotificationAt: null,
      trainingDeadlineAt: new Date(2025, 0, 1),
    });
    expect(errors.trainingDeadlineAt).toBeTruthy();
  });

  it("skips order check when the current field is empty", () => {
    const errors = validateForm({
      ...BASE_FORM,
      trainingDeadlineAt: null,
    });
    expect(errors.trainingDeadlineAt).toBeUndefined();
  });
});
