import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { calculateMentorshipSlots } from "@/pages/PersonalDashboard/utils/mentorshipRounds";

describe("calculateMentorshipSlots", () => {
  // Mock current date: 2023-10-15
  const MOCK_TODAY = "2023-10-15";

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(MOCK_TODAY));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should return default initial state when the list is empty", () => {
    const result = calculateMentorshipSlots([]);
    expect(result).toEqual({
      feedbackRoundId: null,
      isFeedbackEnabled: false,
      regRoundId: null,
      isRegistrationOpen: false,
      matchResultRoundName: "",
      canViewMatch: false,
    });
  });

  it("should enable canViewMatch when today is within the announcement period", () => {
    const rounds = [
      {
        id: "round-active",
        name: "Spring 2024",
        timeline: {
          promotionStartAt: "2023-09-01",
          matchNotificationAt: "2023-10-10", // 10-15 is after this
          feedbackDeadlineAt: "2023-10-20", // 10-15 is before this
        },
      },
    ];

    const result = calculateMentorshipSlots(rounds);
    expect(result.canViewMatch).toBe(true);
    expect(result.matchResultRoundName).toBe("Spring 2024");
  });

  it("should disable canViewMatch when today is before the notification date", () => {
    const rounds = [
      {
        id: "round-future",
        name: "Autumn 2024",
        timeline: {
          promotionStartAt: "2023-10-01",
          matchNotificationAt: "2023-11-01", // 10-15 is before this
          feedbackDeadlineAt: "2023-11-15",
        },
      },
    ];

    const result = calculateMentorshipSlots(rounds);
    expect(result.canViewMatch).toBe(false);
    // Should still pick up the name from lastStartedRound as a fallback
    expect(result.matchResultRoundName).toBe("Autumn 2024");
  });

  it("should correctly identify a round that is currently open for registration", () => {
    const rounds = [
      {
        id: "round-1",
        timeline: {
          promotionStartAt: "2023-10-01",
          applicationDeadlineAt: "2023-10-20", // Today (10-15) is within this range
        },
      },
    ];

    const result = calculateMentorshipSlots(rounds);
    expect(result.regRoundId).toBe("round-1");
    expect(result.isRegistrationOpen).toBe(true);
  });

  it("should correctly identify a round in the feedback phase", () => {
    const rounds = [
      {
        id: "round-old",
        timeline: {
          promotionStartAt: "2023-08-01",
          meetingsCompletionDeadlineAt: "2023-10-10", // Meetings already completed
          feedbackDeadlineAt: "2023-10-20", // Before feedback deadline
        },
      },
    ];

    const result = calculateMentorshipSlots(rounds);
    expect(result.feedbackRoundId).toBe("round-old");
    expect(result.isFeedbackEnabled).toBe(true);
  });

  it("should return regRoundId but set isRegistrationOpen to false when registration is closed but the round has started", () => {
    const rounds = [
      {
        id: "round-closed",
        timeline: {
          promotionStartAt: "2023-09-01",
          applicationDeadlineAt: "2023-10-01", // Today (10-15) is past the deadline
        },
      },
    ];

    const result = calculateMentorshipSlots(rounds);
    expect(result.regRoundId).toBe("round-closed");
    expect(result.isRegistrationOpen).toBe(false); // Viewable only, not open for registration
  });

  it("should sort rounds by promotionStartAt in descending order and pick the latest one", () => {
    const rounds = [
      {
        id: "round-older",
        timeline: {
          promotionStartAt: "2023-01-01",
          applicationDeadlineAt: "2023-01-10",
        },
      },
      {
        id: "round-newer",
        timeline: {
          promotionStartAt: "2023-09-01",
          applicationDeadlineAt: "2023-09-10",
        },
      },
    ];

    const result = calculateMentorshipSlots(rounds);
    // Both rounds are finished, but the newer one should be selected as the viewable slot
    expect(result.regRoundId).toBe("round-newer");
    expect(result.isRegistrationOpen).toBe(false);
  });

  it("should filter out invalid rounds that are missing promotionStartAt", () => {
    const rounds = [
      { id: "invalid", timeline: {} },
      {
        id: "valid",
        timeline: {
          promotionStartAt: "2023-10-01",
          applicationDeadlineAt: "2023-10-20",
        },
      },
    ];

    const result = calculateMentorshipSlots(rounds);
    expect(result.regRoundId).toBe("valid");
  });

  it("combined scenario: both a feedback round and an active registration round exist", () => {
    const rounds = [
      {
        id: "active-reg",
        timeline: {
          promotionStartAt: "2023-10-10",
          applicationDeadlineAt: "2023-10-25",
        },
      },
      {
        id: "in-feedback",
        timeline: {
          promotionStartAt: "2023-08-01",
          meetingsCompletionDeadlineAt: "2023-10-01",
          feedbackDeadlineAt: "2023-10-30",
        },
      },
    ];

    const result = calculateMentorshipSlots(rounds);
    expect(result.feedbackRoundId).toBe("in-feedback");
    expect(result.isFeedbackEnabled).toBe(true);
    expect(result.regRoundId).toBe("active-reg");
    expect(result.isRegistrationOpen).toBe(true);
  });
});
