import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  formatInTz,
  formatLocalYmd,
  todayInTz,
  nowInTz,
  localToUtcIso,
  getDaysSince,
  formatTimezoneLabel,
} from "@/utils/dateTime";

describe("formatInTz", () => {
  it("returns null for null input", () => {
    expect(formatInTz(null, "America/New_York", "yyyy-MM-dd")).toBeNull();
  });

  it("returns null for empty string input", () => {
    expect(formatInTz("", "America/New_York", "yyyy-MM-dd")).toBeNull();
  });

  it("returns null for invalid ISO string", () => {
    expect(
      formatInTz("not-a-date", "America/New_York", "yyyy-MM-dd"),
    ).toBeNull();
  });

  it("formats a UTC ISO string in the given timezone", () => {
    // 2024-03-15T12:00:00Z is noon UTC, which is 8am in America/New_York (EDT, UTC-4)
    expect(
      formatInTz("2024-03-15T12:00:00Z", "America/New_York", "yyyy-MM-dd"),
    ).toBe("2024-03-15");
    expect(
      formatInTz("2024-03-15T12:00:00Z", "America/New_York", "HH:mm"),
    ).toBe("08:00");
  });

  it("handles cross-day UTC shift: UTC midnight is previous day in UTC-5", () => {
    // 2024-01-15T02:00:00Z is 2am UTC → 9pm Jan 14 in America/New_York (EST, UTC-5)
    expect(
      formatInTz("2024-01-15T02:00:00Z", "America/New_York", "yyyy-MM-dd"),
    ).toBe("2024-01-14");
  });

  it("handles DST spring-forward boundary in America/New_York", () => {
    // 2024-03-10: clocks spring forward at 2am → 3am in New York
    // 2024-03-10T07:00:00Z = 3am EDT (after spring forward)
    expect(
      formatInTz("2024-03-10T07:00:00Z", "America/New_York", "HH:mm"),
    ).toBe("03:00");
  });

  it("falls back to UTC when no timezone provided", () => {
    expect(formatInTz("2024-06-01T10:30:00Z", null, "HH:mm")).toBe("10:30");
    expect(formatInTz("2024-06-01T10:30:00Z", "", "HH:mm")).toBe("10:30");
  });

  it("formats with different patterns", () => {
    expect(formatInTz("2024-06-15T00:00:00Z", "UTC", "MMM d, yyyy")).toBe(
      "Jun 15, 2024",
    );
    expect(formatInTz("2024-06-15T00:00:00Z", "UTC", "yyyy-MM-dd")).toBe(
      "2024-06-15",
    );
  });

  it("handles Asia/Shanghai (UTC+8) correctly", () => {
    // 2024-01-01T20:00:00Z = Jan 2 04:00 in Asia/Shanghai
    expect(
      formatInTz("2024-01-01T20:00:00Z", "Asia/Shanghai", "yyyy-MM-dd"),
    ).toBe("2024-01-02");
  });
});

describe("formatLocalYmd", () => {
  it("formats a date in local time as YYYY-MM-DD", () => {
    expect(formatLocalYmd(new Date(2024, 0, 5))).toBe("2024-01-05");
    expect(formatLocalYmd(new Date(2024, 11, 31))).toBe("2024-12-31");
  });

  it("zero-pads month and day", () => {
    expect(formatLocalYmd(new Date(2024, 2, 3))).toBe("2024-03-03");
  });

  it("uses local time, not UTC", () => {
    // Construct a date at local midnight — getFullYear/Month/Date must match
    const d = new Date(2024, 5, 15); // June 15, 2024 local midnight
    expect(formatLocalYmd(d)).toBe("2024-06-15");
  });
});

describe("getDaysSince", () => {
  const MOCK_NOW = new Date("2025-01-10T00:00:00Z");

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(MOCK_NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const testCases = [
    { date: "2025-01-10", expected: 0 },
    { date: "2025-01-09", expected: 1 },
    { date: "2024-12-11", expected: 30 },
    { date: "2025-01-11", expected: 1 },
    { date: null, expected: 999 },
    { date: "", expected: 999 },
  ];

  it.each(testCases)(
    'should return $expected days for date "$date" relative to 2025-01-10',
    ({ date, expected }) => {
      expect(getDaysSince(date)).toBe(expected);
    },
  );
});

describe("formatTimezoneLabel", () => {
  it("formats a timezone label with city and UTC offset", () => {
    const result = formatTimezoneLabel("America/Los_Angeles");
    expect(result).toMatch(/Los Angeles \(UTC[-+]?\d+\)/);
  });

  it("handles city names with underscores", () => {
    const result = formatTimezoneLabel("America/New_York");
    expect(result).toContain("New York");
  });
});

describe("todayInTz", () => {
  const MOCK_NOW = new Date("2024-03-15T06:00:00Z"); // 2am EST (UTC-4 in March)

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(MOCK_NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns a plain Date at local midnight for the given timezone", () => {
    const result = todayInTz("America/New_York");
    expect(result).toBeInstanceOf(Date);
    // 06:00 UTC = 02:00 EST → still Mar 15 in New York
    expect(result.getFullYear()).toBe(2024);
    expect(result.getMonth()).toBe(2); // March (0-indexed)
    expect(result.getDate()).toBe(15);
    expect(result.getHours()).toBe(0);
    expect(result.getMinutes()).toBe(0);
  });

  it("reflects cross-day offset: UTC midnight is previous day in UTC-5", () => {
    vi.setSystemTime(new Date("2024-01-15T02:00:00Z")); // 9pm Jan 14 in New York (EST)
    const result = todayInTz("America/New_York");
    expect(result.getDate()).toBe(14);
  });
});

describe("nowInTz", () => {
  const MOCK_NOW = new Date("2024-06-15T14:30:00Z");

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(MOCK_NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns timezone-aware hours and minutes", () => {
    const result = nowInTz("America/New_York"); // UTC-4 in June
    expect(result.getHours()).toBe(10);
    expect(result.getMinutes()).toBe(30);
  });

  it("returns timezone-aware date in Asia/Shanghai (UTC+8)", () => {
    vi.setSystemTime(new Date("2024-01-01T20:00:00Z")); // Jan 2 04:00 in Shanghai
    const result = nowInTz("Asia/Shanghai");
    expect(result.getDate()).toBe(2);
    expect(result.getHours()).toBe(4);
  });
});

describe("localToUtcIso", () => {
  it("converts a local date+time to UTC ISO string", () => {
    // Jan 15 2024 10:00 in New York (EST = UTC-5) → 15:00 UTC
    const dateObj = new Date(2024, 0, 15); // local midnight, components used by function
    expect(localToUtcIso(dateObj, "10:00", "America/New_York")).toBe(
      "2024-01-15T15:00:00Z",
    );
  });

  it("handles addDays for overnight meetings", () => {
    const dateObj = new Date(2024, 0, 15);
    expect(localToUtcIso(dateObj, "00:30", "America/New_York", 1)).toBe(
      "2024-01-16T05:30:00Z",
    );
  });

  it("returns correct UTC when timezone is ahead of UTC (Asia/Shanghai UTC+8)", () => {
    // Jan 15 2024 08:00 Shanghai (UTC+8) → 00:00 UTC
    const dateObj = new Date(2024, 0, 15);
    expect(localToUtcIso(dateObj, "08:00", "Asia/Shanghai")).toBe(
      "2024-01-15T00:00:00Z",
    );
  });
});
