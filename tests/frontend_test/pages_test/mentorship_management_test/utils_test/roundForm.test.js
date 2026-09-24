import { describe, it, expect } from "vitest";
import {
  validateForm,
  EMPTY_FORM,
  FLATTENED_TIMELINE_FIELDS,
  buildUpsertPayload,
  getSeasonDefaults,
} from "@/pages/MentorshipManagement/utils/roundForm";

const BASE_FORM = {
  ...EMPTY_FORM,
  name: "Mentorship 2026 Spring",
  requiredMeetings: 5,
  promotionStartAt: new Date(2025, 11, 18),
  mentorApplicationDeadlineAt: new Date(2025, 11, 25),
  menteeApplicationDeadlineAt: new Date(2025, 11, 25),
  onboardingDeadlineAt: new Date(2026, 1, 9),
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
    "onboardingDeadlineAt",
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
    "uses the latest sign-up deadline as the lower bound for onboarding",
    (overrides) => {
      const invalid = validateForm({
        ...BASE_FORM,
        ...overrides,
        onboardingNotificationAt: new Date(2026, 0, 15),
      });
      expect(invalid.onboardingNotificationAt).toBeDefined();

      const valid = validateForm({
        ...BASE_FORM,
        ...overrides,
        onboardingNotificationAt: new Date(2026, 0, 21),
      });
      expect(valid).toEqual({}); // Onboarding notification is valid once it exceeds the high watermark.
    },
  );

  it("rejects onboardingDeadlineAt before its effective ancestor when onboardingNotificationAt is empty", () => {
    const errors = validateForm({
      ...BASE_FORM,
      onboardingNotificationAt: null,
      onboardingDeadlineAt: new Date(2025, 0, 1),
    });
    expect(errors.onboardingDeadlineAt).toBeTruthy();
  });

  it("skips order check when the current field is empty", () => {
    const errors = validateForm({
      ...BASE_FORM,
      onboardingNotificationAt: null,
    });
    expect(errors.onboardingNotificationAt).toBeUndefined();
  });

  it("rejects firstMeetingDeadlineAt before matchNotificationAt", () => {
    const errors = validateForm({
      ...BASE_FORM,
      firstMeetingDeadlineAt: new Date(2026, 1, 11),
    });
    expect(errors.firstMeetingDeadlineAt).toMatch(/Matching Admin Action/);
  });
});

describe("timeline fields", () => {
  it("puts the first-contact deadline on firstMeetingDeadlineAt", () => {
    const keys = FLATTENED_TIMELINE_FIELDS.map(({ key }) => key);
    expect(keys).toContain("firstMeetingDeadlineAt");
    expect(keys).toContain("onboardingNotificationAt");
    expect(keys).toContain("onboardingDeadlineAt");
    expect(keys).not.toContain("matchingCompletedAt");
    expect(keys).not.toContain("trainingNotificationAt");
    expect(keys).not.toContain("trainingDeadlineAt");
  });

  it("sends every form date under its own key", () => {
    const payload = buildUpsertPayload({
      ...BASE_FORM,
      onboardingNotificationAt: new Date(2026, 1, 2),
      firstMeetingDeadlineAt: new Date(2026, 1, 26),
    });
    expect(payload.timeline.onboardingNotificationAt).toBe(
      "2026-02-03T07:59:59Z",
    );
    expect(payload.timeline.onboardingDeadlineAt).toBe("2026-02-10T07:59:59Z");
    expect(payload.timeline.firstMeetingDeadlineAt).toBe(
      "2026-02-27T07:59:59Z",
    );
    expect(payload.timeline).not.toHaveProperty("matchingCompletedAt");
  });

  it.each([
    ["Spring", 2026, [1, 9], [1, 26]],
    ["Summer", 2026, [4, 9], [4, 26]],
    ["Fall", 2026, [8, 9], [8, 26]],
  ])(
    "keeps the %s preset's onboarding and first-contact dates",
    (season, year, [onbMonth, onbDay], [firstMonth, firstDay]) => {
      const defaults = getSeasonDefaults(season, year);
      expect(defaults.onboardingDeadlineAt).toEqual(
        new Date(year, onbMonth, onbDay),
      );
      expect(defaults.firstMeetingDeadlineAt).toEqual(
        new Date(year, firstMonth, firstDay),
      );
      expect(defaults).not.toHaveProperty("matchingCompletedAt");
    },
  );
});
