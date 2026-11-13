import { describe, it, expect } from "vitest";

import {
  BannerAction,
  BannerKind,
  BannerTone,
  StepState,
  mentorshipBannerState,
} from "@/pages/PersonalDashboard/utils/mentorshipBannerState";

// The viewer's zone is behind UTC, so a date formatted in UTC by mistake
// lands on the wrong calendar day in every assertion below.
const TZ = "America/New_York";

const REG_ROUND = {
  id: 42,
  name: "2027 Spring",
  status: "active",
  timeline: {
    promotionStartAt: "2026-12-18T08:00:00Z",
    onboardingDeadlineAt: "2027-01-20T03:00:00Z", // Jan 19, 22:00 in New York
    matchNotificationAt: "2027-02-13T03:30:00Z", // Feb 12, 22:30 in New York
  },
};
const DEADLINE = REG_ROUND.timeline.onboardingDeadlineAt;

const PAST_ROUND = {
  id: 41,
  name: "2026 Fall",
  status: "completed",
  timeline: { promotionStartAt: "2026-08-18T07:00:00Z" },
};
// Marked upcoming but already promoted: status is not what picks the next round.
const UPCOMING_BY_STATUS_ONLY = {
  id: 43,
  name: "Upcoming By Status",
  status: "upcoming",
  timeline: { promotionStartAt: "2026-11-01T07:00:00Z" },
};
const LATER_ROUND = {
  id: 45,
  name: "2027 Fall",
  status: "upcoming",
  timeline: { promotionStartAt: "2027-08-18T07:00:00Z" },
};
const NEXT_ROUND = {
  id: 44,
  name: "2027 Summer",
  status: "upcoming",
  timeline: { promotionStartAt: "2027-04-18T07:00:00Z" },
};
const UNDATED_ROUND = {
  id: 46,
  name: "Undated",
  status: "upcoming",
  timeline: { promotionStartAt: null },
};
const ROUNDS = [
  LATER_ROUND,
  PAST_ROUND,
  UPCOMING_BY_STATUS_ONLY,
  REG_ROUND,
  UNDATED_ROUND,
  NEXT_ROUND,
];

const OPEN_NOW = new Date("2027-01-05T15:00:00Z");

const build = (overrides = {}) =>
  mentorshipBannerState({
    now: OPEN_NOW,
    timezone: TZ,
    regRoundId: REG_ROUND.id,
    regRoundName: REG_ROUND.name,
    regTimeline: REG_ROUND.timeline,
    isRegistrationOpen: true,
    registrationDeadlineAt: DEADLINE,
    isRegistered: false,
    isTrainingDone: false,
    canViewMatch: false,
    matchStatus: null,
    rounds: ROUNDS,
    ...overrides,
  });

const stepStates = (state) => state.steps?.map((s) => s.state);

describe("mentorshipBannerState", () => {
  describe("no round open", () => {
    it("names the earliest round whose promotion is still ahead", () => {
      const state = build({ regRoundId: null, regRoundName: "" });

      expect(state.kind).toBe(BannerKind.NO_ROUND);
      expect(state.title).toBe("Mentorship");
      expect(state.steps).toBeNull();
      expect(state.lead).toBe("Next:");
      expect(state.next).toBe(
        "registration for 2027 Summer opens Apr 18. We'll email you when it does.",
      );
      expect(state.action).toBeNull();
      expect(state.showProfileLine).toBe(false);
    });

    it("ignores rounds that are upcoming by status but already promoted", () => {
      const state = build({
        regRoundId: null,
        rounds: [PAST_ROUND, UPCOMING_BY_STATUS_ONLY, UNDATED_ROUND],
      });

      expect(state.next).toBe(
        "register when the next round opens. We'll email you when it does.",
      );
    });

    it("says only that one will open when no round is scheduled", () => {
      const state = build({ regRoundId: null, rounds: [] });

      expect(state.kind).toBe(BannerKind.NO_ROUND);
      expect(state.next).toBe(
        "register when the next round opens. We'll email you when it does.",
      );
    });

    it("treats a registered round whose cycle is over as no round open", () => {
      const state = build({
        now: new Date("2027-03-20T00:00:00Z"),
        isRegistrationOpen: false,
        isRegistered: true,
        isTrainingDone: true,
        canViewMatch: false,
        matchStatus: "matched",
      });

      expect(state.kind).toBe(BannerKind.NO_ROUND);
      expect(state.title).toBe("Mentorship");
      expect(state.next).toMatch(/2027 Summer opens Apr 18/);
    });

    it("treats an unregistered viewer as no round open once matches are announced", () => {
      const state = build({
        now: new Date("2027-02-14T00:00:00Z"),
        isRegistrationOpen: false,
        canViewMatch: true,
      });

      expect(state.kind).toBe(BannerKind.NO_ROUND);
    });

    it("treats an unregistered viewer as no round open once the announcement date passes", () => {
      const state = build({
        now: new Date("2027-02-13T03:30:00Z"),
        isRegistrationOpen: false,
      });

      expect(state.kind).toBe(BannerKind.NO_ROUND);
    });
  });

  describe("registration open, not registered", () => {
    it("asks for registration by the deadline in the viewer's zone", () => {
      const state = build();

      expect(state.kind).toBe(BannerKind.REGISTER);
      expect(state.title).toBe("2027 Spring");
      expect(state.tone).toBe(BannerTone.NORMAL);
      expect(state.next).toBe("register by Jan 19.");
      expect(state.action).toBe(BannerAction.REGISTER);
      expect(state.showProfileLine).toBe(true);
      expect(stepStates(state)).toEqual([
        StepState.CURRENT,
        StepState.UPCOMING,
        StepState.UPCOMING,
      ]);
    });

    it("is not amber with exactly 3 days left", () => {
      const state = build({ now: new Date("2027-01-17T03:00:00Z") });

      expect(state.tone).toBe(BannerTone.NORMAL);
      expect(state.next).toBe("register by Jan 19.");
    });

    it("turns amber with under 3 days left and counts calendar days", () => {
      const state = build({ now: new Date("2027-01-17T03:01:00Z") });

      expect(state.tone).toBe(BannerTone.AMBER);
      expect(state.next).toBe("register by Jan 19 (in 3 days).");
    });

    it("says in 1 day the day before", () => {
      const state = build({ now: new Date("2027-01-19T02:00:00Z") });

      expect(state.next).toBe("register by Jan 19 (in 1 day).");
    });

    it("says today on the deadline's own day in the viewer's zone", () => {
      // Still Jan 19 in New York though already Jan 19 15:00 UTC.
      const state = build({ now: new Date("2027-01-19T15:00:00Z") });

      expect(state.tone).toBe(BannerTone.AMBER);
      expect(state.next).toBe("register by Jan 19 (today).");
    });

    it("ticks training done before registering while Register stays current", () => {
      const state = build({ isTrainingDone: true });

      expect(stepStates(state)).toEqual([
        StepState.CURRENT,
        StepState.DONE,
        StepState.UPCOMING,
      ]);
    });

    it("falls back to the round's onboarding deadline", () => {
      const state = build({ registrationDeadlineAt: null });

      expect(state.next).toBe("register by Jan 19.");
    });
  });

  describe("registration closed, not registered", () => {
    it("marks Register missed and offers nothing", () => {
      const state = build({
        now: new Date("2027-01-25T00:00:00Z"),
        isRegistrationOpen: false,
      });

      expect(state.kind).toBe(BannerKind.REGISTRATION_CLOSED);
      expect(state.tone).toBe(BannerTone.MUTED);
      expect(state.lead).toBeNull();
      expect(state.next).toBe(
        "Registration for 2027 Spring has closed. You can register when the next round opens. We'll email you when it does.",
      );
      expect(state.action).toBeNull();
      expect(state.showProfileLine).toBe(false);
      expect(stepStates(state)).toEqual([
        StepState.FAILED,
        StepState.UPCOMING,
        StepState.UPCOMING,
      ]);
    });
  });

  describe("registered, training not done", () => {
    const registered = { isRegistered: true };

    it("points at training by the deadline", () => {
      const state = build(registered);

      expect(state.kind).toBe(BannerKind.TRAINING);
      expect(state.tone).toBe(BannerTone.NORMAL);
      expect(state.next).toBe("finish your onboarding training by Jan 19.");
      expect(state.action).toBe(BannerAction.TRAINING);
      expect(state.showProfileLine).toBe(true);
      expect(stepStates(state)).toEqual([
        StepState.DONE,
        StepState.CURRENT,
        StepState.UPCOMING,
      ]);
    });

    it("turns amber within 3 days", () => {
      const state = build({
        ...registered,
        now: new Date("2027-01-18T12:00:00Z"),
      });

      expect(state.tone).toBe(BannerTone.AMBER);
      expect(state.next).toBe(
        "finish your onboarding training by Jan 19 (in 1 day).",
      );
    });

    it("stays on the training step once registration has closed", () => {
      const state = build({
        ...registered,
        isRegistrationOpen: false,
        now: new Date("2027-01-19T15:00:00Z"),
      });

      expect(state.kind).toBe(BannerKind.TRAINING);
      expect(state.next).toBe(
        "finish your onboarding training by Jan 19 (today).",
      );
    });

    it("is overdue after the deadline and names the matching date", () => {
      const state = build({
        ...registered,
        isRegistrationOpen: false,
        now: new Date("2027-01-20T03:00:00Z"),
      });

      expect(state.kind).toBe(BannerKind.TRAINING_OVERDUE);
      expect(state.tone).toBe(BannerTone.AMBER);
      expect(state.lead).toBe("Overdue:");
      expect(state.next).toBe(
        "your onboarding training was due Jan 19. Finish it before matches are made on Feb 12, or you can't be matched this round.",
      );
      expect(state.action).toBe(BannerAction.TRAINING);
      expect(state.showProfileLine).toBe(true);
    });

    it("is overdue without a matching date when the round has none", () => {
      const state = build({
        ...registered,
        isRegistrationOpen: false,
        now: new Date("2027-01-25T00:00:00Z"),
        regTimeline: { ...REG_ROUND.timeline, matchNotificationAt: null },
      });

      expect(state.next).toBe(
        "your onboarding training was due Jan 19. Finish it before matches are made, or you can't be matched this round.",
      );
    });
  });

  describe("registered and trained, before matches", () => {
    it("names the announcement date", () => {
      const state = build({ isRegistered: true, isTrainingDone: true });

      expect(state.kind).toBe(BannerKind.AWAITING_MATCHES);
      expect(state.tone).toBe(BannerTone.NORMAL);
      expect(state.next).toBe("matches are announced Feb 12.");
      expect(state.action).toBeNull();
      expect(state.showProfileLine).toBe(true);
      expect(stepStates(state)).toEqual([
        StepState.DONE,
        StepState.DONE,
        StepState.CURRENT,
      ]);
    });

    it("says soon when the round has no announcement date", () => {
      const state = build({
        isRegistered: true,
        isTrainingDone: true,
        regTimeline: { ...REG_ROUND.timeline, matchNotificationAt: null },
      });

      expect(state.next).toBe("matches will be announced soon.");
    });
  });

  describe("matches announced, registered", () => {
    const announced = {
      now: new Date("2027-02-14T00:00:00Z"),
      isRegistrationOpen: false,
      isRegistered: true,
      isTrainingDone: true,
      canViewMatch: true,
    };

    it("points a matched viewer at the result with no bar", () => {
      const state = build({ ...announced, matchStatus: "matched" });

      expect(state.kind).toBe(BannerKind.MATCHED);
      expect(state.steps).toBeNull();
      expect(state.next).toBe(
        "see who you're matched with. Your meetings for this round are in Mentorship Participation below.",
      );
      expect(state.action).toBe(BannerAction.MATCH_RESULT);
      expect(state.showProfileLine).toBe(false);
    });

    it("tells an unmatched viewer, greyed and without an action", () => {
      const state = build({ ...announced, matchStatus: "unmatched" });

      expect(state.kind).toBe(BannerKind.UNMATCHED);
      expect(state.steps).toBeNull();
      expect(state.tone).toBe(BannerTone.MUTED);
      expect(state.lead).toBeNull();
      expect(state.next).toBe(
        "You weren't matched this round. You can register again when the next round opens.",
      );
      expect(state.action).toBeNull();
      expect(state.showProfileLine).toBe(false);
    });

    it.each(["pending", "unknown", null])(
      "treats a %s status as still waiting for matches",
      (matchStatus) => {
        const state = build({ ...announced, matchStatus });

        expect(state.kind).toBe(BannerKind.AWAITING_MATCHES);
        // The announcement date is behind us, so it is not repeated.
        expect(state.next).toBe("matches will be announced soon.");
      },
    );
  });

  it("does not show a round whose registration has not started", () => {
    const state = build({
      now: new Date("2026-12-01T00:00:00Z"),
      isRegistrationOpen: false,
    });

    expect(state.kind).toBe(BannerKind.NO_ROUND);
    expect(state.next).toBe(
      "registration for 2027 Spring opens Dec 18. We'll email you when it does.",
    );
  });
});
