import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  calculateMentorshipSlots,
  calculateRoundStatus,
} from "@/pages/PersonalDashboard/utils/mentorshipRounds";

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

describe("calculateRoundStatus", () => {
  const MOCK_TODAY = "2026-03-18T12:00:00Z";

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(MOCK_TODAY));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should return empty sortedRounds and null activeRoundId for empty input", () => {
    const result = calculateRoundStatus([]);
    expect(result.sortedRounds).toEqual([]);
    expect(result.activeRoundId).toBeNull();
  });

  it("should mark a round as active when today is within its date range", () => {
    const rounds = [
      {
        id: "round-active",
        timeline: {
          matchNotificationAt: "2026-01-01",
          meetingsCompletionDeadlineAt: "2026-12-31",
        },
      },
    ];
    const result = calculateRoundStatus(rounds);
    expect(result.sortedRounds[0].status).toBe("active");
    expect(result.activeRoundId).toBe("round-active");
  });

  it("should mark a round as upcoming when roundStart is in the future", () => {
    const rounds = [
      {
        id: "round-future",
        timeline: {
          promotionStartAt: "2027-01-01",
          meetingsCompletionDeadlineAt: "2027-12-31",
        },
      },
    ];
    const result = calculateRoundStatus(rounds);
    expect(result.sortedRounds[0].status).toBe("upcoming");
    expect(result.activeRoundId).toBe("round-future");
  });

  it("should mark a round as completed when today is past meetingsCompletionDeadlineAt", () => {
    const rounds = [
      {
        id: "round-done",
        timeline: {
          promotionStartAt: "2025-01-01",
          meetingsCompletionDeadlineAt: "2025-12-31",
        },
      },
    ];
    const result = calculateRoundStatus(rounds);
    expect(result.sortedRounds[0].status).toBe("completed");
    expect(result.activeRoundId).toBeNull();
  });

  it("should prefer active round over upcoming round for activeRoundId", () => {
    const rounds = [
      {
        id: "round-upcoming",
        timeline: {
          promotionStartAt: "2027-01-01",
          meetingsCompletionDeadlineAt: "2027-12-31",
        },
      },
      {
        id: "round-active",
        timeline: {
          matchNotificationAt: "2026-01-01",
          meetingsCompletionDeadlineAt: "2026-12-31",
        },
      },
    ];
    const result = calculateRoundStatus(rounds);
    expect(result.activeRoundId).toBe("round-active");
  });

  it("should sort rounds in descending order by end date", () => {
    const rounds = [
      {
        id: "round-earlier",
        timeline: {
          promotionStartAt: "2025-01-01",
          meetingsCompletionDeadlineAt: "2025-06-30",
        },
      },
      {
        id: "round-later",
        timeline: {
          promotionStartAt: "2025-07-01",
          meetingsCompletionDeadlineAt: "2025-12-31",
        },
      },
    ];
    const result = calculateRoundStatus(rounds);
    expect(result.sortedRounds[0].id).toBe("round-later");
    expect(result.sortedRounds[1].id).toBe("round-earlier");
  });

  it("should use promotionStartAt as roundStart when matchNotificationAt is absent", () => {
    const rounds = [
      {
        id: "round-promo",
        timeline: {
          promotionStartAt: "2026-01-01",
          meetingsCompletionDeadlineAt: "2026-12-31",
        },
      },
    ];
    const result = calculateRoundStatus(rounds);
    expect(result.sortedRounds[0].status).toBe("active");
  });
});
