import { describe, test, expect } from "vitest";

import {
  LEAVE_CALENDAR_ZONE_LABEL,
  formatBusinessDate,
  formatBusinessRange,
  formatTimeSpan,
} from "@/pages/Leave/utils/leaveDates";

describe("formatBusinessDate", () => {
  test("renders the day the server sent, not the viewer's day", () => {
    // A business date is a Beijing calendar day and carries no time. Passing it
    // through the browser's clock is what turns 1 October into 30 September for
    // anybody west of UTC, so nothing here may construct a Date.
    expect(formatBusinessDate("2026-10-01")).toBe("Oct 1, 2026");
  });

  test("holds at both ends of a month", () => {
    expect(formatBusinessDate("2026-01-01")).toBe("Jan 1, 2026");
    expect(formatBusinessDate("2026-12-31")).toBe("Dec 31, 2026");
  });

  test("renders nothing for nothing", () => {
    expect(formatBusinessDate(null)).toBe("");
    expect(formatBusinessDate("")).toBe("");
  });
});

describe("formatBusinessRange", () => {
  test("a single day is shown once, not as a range of itself", () => {
    expect(formatBusinessRange("2026-08-13", "2026-08-13")).toBe(
      "Aug 13, 2026",
    );
  });

  test("a range within one year names the year once", () => {
    expect(formatBusinessRange("2026-08-13", "2026-08-15")).toBe(
      "Aug 13 – Aug 15, 2026",
    );
  });

  test("a range across new year names both years", () => {
    expect(formatBusinessRange("2026-12-30", "2027-01-02")).toBe(
      "Dec 30, 2026 – Jan 2, 2027",
    );
  });
});

describe("formatTimeSpan", () => {
  test("renders the wall clock the request carries", () => {
    expect(formatTimeSpan("09:00:00", "13:30:00")).toBe("09:00 – 13:30");
  });

  test("renders nothing when a request covers whole days", () => {
    expect(formatTimeSpan(null, null)).toBe("");
  });
});

describe("LEAVE_CALENDAR_ZONE_LABEL", () => {
  test("names the zone the dates belong to", () => {
    // Company holidays are one calendar for the whole company, so the label is
    // fixed rather than taken from the viewer's profile.
    expect(LEAVE_CALENDAR_ZONE_LABEL).toContain("Shanghai");
  });
});
