import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  formatInTz,
  formatDateWithZone,
  formatDateTimeWithZone,
  formatDateTimeRangeWithZone,
  formatLocalYmd,
  todayInTz,
  nowInTz,
  localToUtcIso,
  getDaysSince,
  HALF_HOUR_SLOTS,
  isSameLocalDay,
  minutesIntoLocalDay,
  hhMmToMinutes,
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

describe("formatDateWithZone", () => {
  it("returns null for missing iso or tz", () => {
    expect(formatDateWithZone(null, "America/New_York")).toBeNull();
    expect(formatDateWithZone("2024-03-15T12:00:00Z", null)).toBeNull();
  });

  it("appends the IANA zone name to the formatted date, with no time-of-day", () => {
    expect(formatDateWithZone("2024-03-15T12:00:00Z", "America/New_York")).toBe(
      "2024-03-15 America/New_York",
    );
  });
});

describe("formatDateTimeWithZone", () => {
  it("returns null for missing iso or tz", () => {
    expect(formatDateTimeWithZone(null, "America/New_York")).toBeNull();
    expect(formatDateTimeWithZone("2024-03-15T12:00:00Z", null)).toBeNull();
  });

  it("appends the IANA zone name to the formatted instant", () => {
    expect(
      formatDateTimeWithZone("2024-03-15T12:00:00Z", "America/New_York"),
    ).toBe("2024-03-15 08:00 America/New_York");
  });
});

describe("formatDateTimeRangeWithZone", () => {
  it("returns null when any input is missing", () => {
    expect(
      formatDateTimeRangeWithZone(
        null,
        "2024-03-15T13:00:00Z",
        "America/New_York",
      ),
    ).toBeNull();
    expect(
      formatDateTimeRangeWithZone(
        "2024-03-15T12:00:00Z",
        null,
        "America/New_York",
      ),
    ).toBeNull();
    expect(
      formatDateTimeRangeWithZone(
        "2024-03-15T12:00:00Z",
        "2024-03-15T13:00:00Z",
        null,
      ),
    ).toBeNull();
  });

  it("appends the IANA zone name to the formatted range", () => {
    expect(
      formatDateTimeRangeWithZone(
        "2024-03-15T12:00:00Z",
        "2024-03-15T13:00:00Z",
        "America/New_York",
      ),
    ).toBe("2024-03-15 · 08:00 - 09:00 America/New_York");
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

  it("includes seconds when time string has HH:mm:ss format", () => {
    // Jan 15 2024 10:00:30 in New York (UTC-5) → 15:00:30 UTC
    const dateObj = new Date(2024, 0, 15);
    expect(localToUtcIso(dateObj, "10:00:30", "America/New_York")).toBe(
      "2024-01-15T15:00:30Z",
    );
  });
});

describe("HALF_HOUR_SLOTS", () => {
  it("covers a full day in half-hour steps", () => {
    expect(HALF_HOUR_SLOTS).toHaveLength(48);
    expect(HALF_HOUR_SLOTS[0]).toBe("00:00");
    expect(HALF_HOUR_SLOTS[HALF_HOUR_SLOTS.length - 1]).toBe("23:30");
  });

  it("alternates between the hour and the half hour", () => {
    expect(HALF_HOUR_SLOTS.slice(0, 4)).toEqual([
      "00:00",
      "00:30",
      "01:00",
      "01:30",
    ]);
  });

  it("zero-pads single-digit hours", () => {
    expect(HALF_HOUR_SLOTS).toContain("09:30");
    expect(HALF_HOUR_SLOTS).not.toContain("9:30");
  });

  it("cannot be mutated by a caller", () => {
    // Shared across the meeting log and scheduling forms, so one form must not
    // be able to change what the other offers.
    expect(() => HALF_HOUR_SLOTS.push("24:00")).toThrow();
    expect(HALF_HOUR_SLOTS).toHaveLength(48);
  });
});

describe("isSameLocalDay", () => {
  it("is true for two instants on the same local calendar day", () => {
    expect(
      isSameLocalDay(
        new Date(2024, 2, 15, 0, 0),
        new Date(2024, 2, 15, 23, 59),
      ),
    ).toBe(true);
  });

  it("is false across a local day boundary one minute apart", () => {
    expect(
      isSameLocalDay(
        new Date(2024, 2, 15, 23, 59),
        new Date(2024, 2, 16, 0, 0),
      ),
    ).toBe(false);
  });

  it("compares the calendar day each date carries, not the UTC day", () => {
    // 2024-01-01T20:00Z is already Jan 2 in Shanghai, so a picker sitting on
    // Jan 2 (built by todayInTz) is "today" even though UTC still says Jan 1.
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-01-01T20:00:00Z"));
    try {
      const shanghaiNow = nowInTz("Asia/Shanghai");
      expect(isSameLocalDay(todayInTz("Asia/Shanghai"), shanghaiNow)).toBe(
        true,
      );
      expect(isSameLocalDay(new Date(2024, 0, 1), shanghaiNow)).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("minutesIntoLocalDay", () => {
  it("is zero at local midnight", () => {
    expect(minutesIntoLocalDay(new Date(2024, 2, 15, 0, 0))).toBe(0);
  });

  it("counts hours and minutes since local midnight", () => {
    expect(minutesIntoLocalDay(new Date(2024, 2, 15, 14, 30))).toBe(870);
    expect(minutesIntoLocalDay(new Date(2024, 2, 15, 23, 59))).toBe(1439);
  });

  it("reads the zone-local clock of a timezone-aware date", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-06-15T14:30:00Z"));
    try {
      // 14:30 UTC is 10:30 in New York (UTC-4 in June)
      expect(minutesIntoLocalDay(nowInTz("America/New_York"))).toBe(630);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("hhMmToMinutes", () => {
  it("converts a clock string to minutes since midnight", () => {
    expect(hhMmToMinutes("00:00")).toBe(0);
    expect(hhMmToMinutes("14:30")).toBe(870);
    expect(hhMmToMinutes("23:30")).toBe(1410);
  });

  it("agrees with minutesIntoLocalDay for the same clock time", () => {
    // The pickers compare an offered slot against the current clock, so the two
    // must measure from the same origin.
    expect(hhMmToMinutes("09:45")).toBe(
      minutesIntoLocalDay(new Date(2024, 2, 15, 9, 45)),
    );
  });

  it("ignores a seconds component when one is present", () => {
    expect(hhMmToMinutes("10:15:30")).toBe(615);
  });
});
