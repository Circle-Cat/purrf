import { describe, it, expect } from "vitest";
import {
  attendanceIssueLines,
  firstContactOverdueLine,
  formatPacific,
} from "@/pages/MentorshipManagement/utils/attendanceIssues";

const names = { mentorName: "Dana Wu", menteeName: "Erin Ma" };

describe("attendanceIssueLines", () => {
  it("dates each meeting in Los Angeles time and names the tagged person", () => {
    expect(
      attendanceIssueLines(
        [
          // 02:00 UTC on the 31st is still the 30th in Los Angeles.
          { startDatetime: "2026-08-31T02:00:00Z", note: ["mentee_absent"] },
          {
            startDatetime: "2026-09-13T17:00:00Z",
            note: ["mentor_late", "insufficient_duration"],
          },
        ],
        names,
      ),
    ).toEqual([
      "2026-08-30: Erin Ma absent",
      "2026-09-13: Dana Wu late arrival; Insufficient duration",
    ]);
  });

  it("is empty when no meeting is flagged", () => {
    expect(attendanceIssueLines([], names)).toEqual([]);
  });
});

describe("formatPacific", () => {
  it("shows a time in Los Angeles to the minute", () => {
    expect(formatPacific("2026-10-02T17:30:00Z")).toBe("2026-10-02 10:30");
  });
});

describe("firstContactOverdueLine", () => {
  const NOW = new Date("2026-11-20T12:00:00Z");
  // 07:00 UTC on the 18th is still the 17th in Los Angeles.
  const round = {
    inProgress: true,
    firstMeetingDeadlineAt: "2026-11-18T07:00:00Z",
  };
  const live = { isActive: true, completedMeetingCount: 0 };

  it("flags a live pair with no meeting held after the date", () => {
    expect(firstContactOverdueLine(live, round, NOW)).toBe(
      "No meeting held yet. First contact was due 2026-11-17.",
    );
  });

  it("does not flag a pair that held a meeting", () => {
    expect(
      firstContactOverdueLine(
        { ...live, completedMeetingCount: 1 },
        round,
        NOW,
      ),
    ).toBeNull();
  });

  it("does not flag before the date", () => {
    expect(
      firstContactOverdueLine(live, round, new Date("2026-11-18T06:59:00Z")),
    ).toBeNull();
  });

  it("does not flag an ended pair", () => {
    expect(
      firstContactOverdueLine({ ...live, isActive: false }, round, NOW),
    ).toBeNull();
  });

  it("does not flag outside the round's run or without a date", () => {
    expect(
      firstContactOverdueLine(live, { ...round, inProgress: false }, NOW),
    ).toBeNull();
    expect(
      firstContactOverdueLine(
        live,
        { ...round, firstMeetingDeadlineAt: null },
        NOW,
      ),
    ).toBeNull();
  });
});
