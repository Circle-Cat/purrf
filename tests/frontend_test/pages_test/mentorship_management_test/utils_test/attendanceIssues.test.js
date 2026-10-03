import { describe, it, expect } from "vitest";
import { attendanceIssueLines } from "@/pages/MentorshipManagement/utils/attendanceIssues";

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
