import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  parseDateParts,
  formatDateFromParts,
  formatTimeDuration,
  getDaysSince,
  isValidEmail,
  months,
  years,
  currentYear,
  getDateScore,
  sortExperienceOrEducationList,
  formatTimezoneLabel,
} from "@/pages/Profile/utils";

describe("Profile Utils", () => {
  describe("formatTimezoneLabel", () => {
    it("should correctly format a timezone label", () => {
      const result = formatTimezoneLabel("America/Los_Angeles");
      expect(result).toMatch(/Los Angeles \(UTC[-+]?\d+\)/);

      vi.useRealTimers();
    });

    it("should handle city names with underscores", () => {
      const result = formatTimezoneLabel("America/New_York");
      expect(result).toContain("New York");
    });
  });

  describe("Constants", () => {
    it("months should have 12 valid month names", () => {
      // Verify months array contains all 12 months in order
      expect(months).toHaveLength(12);
      expect(months[0]).toBe("January");
      expect(months[11]).toBe("December");
    });

    it("years should generate 50 years descending from current year", () => {
      // Verify years array generates 50 years descending from currentYear
      expect(years).toHaveLength(50);
      expect(years[0]).toBe(currentYear);
      expect(years[49]).toBe(currentYear - 49);
    });
  });

  describe("parseDateParts", () => {
    /**
     * Test cases include:
     * - Valid date strings
     * - Empty or null values
     * - Invalid format or out-of-range month
     */
    const testCases = [
      { input: "2023-01-01", expected: { month: "January", year: "2023" } },
      { input: "1999-12-31", expected: { month: "December", year: "1999" } },
      { input: "2025-06-15", expected: { month: "June", year: "2025" } },
      { input: "", expected: { month: "", year: "" } },
      { input: null, expected: { month: "", year: "" } },
      { input: undefined, expected: { month: "", year: "" } },
      { input: "invalid-date", expected: { month: "", year: "" } },
      { input: "2023-13-01", expected: { month: "", year: "" } },
    ];

    it.each(testCases)(
      'should parse "$input" to $expected',
      ({ input, expected }) => {
        expect(parseDateParts(input)).toEqual(expected);
      },
    );
  });

  describe("formatDateFromParts", () => {
    /**
     * Test cases include:
     * - Valid month/year combinations
     * - Numeric year input
     * - Missing month or year
     * - Invalid month string
     */
    const testCases = [
      { month: "January", year: "2023", expected: "2023-01-01" },
      { month: "December", year: 2025, expected: "2025-12-01" },
      { month: "September", year: "1990", expected: "1990-09-01" },
      { month: "", year: "2023", expected: null },
      { month: "January", year: "", expected: null },
      { month: null, year: "2023", expected: null },
      { month: "NotAMonth", year: "2023", expected: null },
    ];

    it.each(testCases)(
      'should format ($month, $year) to "$expected"',
      ({ month, year, expected }) => {
        expect(formatDateFromParts(month, year)).toBe(expected);
      },
    );
  });

  describe("formatTimeDuration", () => {
    /**
     * Test cases include:
     * - Full start and end dates
     * - Currently ongoing positions (isCurrent = true)
     * - Only start or only end date provided
     * - Empty values
     */
    const testCases = [
      {
        args: ["September", "2020", "January", "2022", false],
        expected: "Sep 2020 - Jan 2022",
      },
      {
        args: ["September", "2020", "", "", true],
        expected: "Sep 2020 - Present",
      },
      {
        args: ["May", "2023", "June", "2024", true],
        expected: "May 2023 - Present",
      },
      { args: ["March", "2019", "", "", false], expected: "Mar 2019" },
      { args: ["", "", "July", "2025", false], expected: "Jul 2025" },
      { args: ["", "", "", "", false], expected: "" },
    ];

    it.each(testCases)(
      'should format args %j to "$expected"',
      ({ args, expected }) => {
        const [startMonth, startYear, endMonth, endYear, isCurrent] = args;
        expect(
          formatTimeDuration(
            startMonth,
            startYear,
            endMonth,
            endYear,
            isCurrent,
          ),
        ).toBe(expected);
      },
    );
  });

  describe("getDaysSince", () => {
    /**
     * Use a fixed mock date (2025-01-10) to test day differences.
     * Test cases include:
     * - Same day
     * - Past days
     * - Future days
     * - Empty/null input
     */
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

  describe("isValidEmail", () => {
    /**
     * Test cases include:
     * - Valid email addresses
     * - Invalid formats (missing @, missing domain, contains spaces, empty string)
     */
    const testCases = [
      { email: "test@example.com", expected: true },
      { email: "user.name@domain.co", expected: true },
      { email: "user+tag@domain.org", expected: true },
      { email: "invalid-email", expected: false },
      { email: "test@domain", expected: false },
      { email: "@domain.com", expected: false },
      { email: "user@.com", expected: false },
      { email: "user @domain.com", expected: false },
      { email: "", expected: false },
    ];

    it.each(testCases)(
      'should return $expected for email "$email"',
      ({ email, expected }) => {
        expect(isValidEmail(email)).toBe(expected);
      },
    );
  });

  describe("getDateScore", () => {
    /**
     * Logic: year * 12 + monthIndex (0-11)
     * If year is missing, returns 0.
     * If month is invalid/missing, defaults to index 0.
     */
    const testCases = [
      { year: 2023, month: "January", expected: 2023 * 12 + 0 }, // 24276
      { year: "2023", month: "December", expected: 2023 * 12 + 11 }, // 24287
      { year: 2020, month: "June", expected: 2020 * 12 + 5 },
      // Edge cases
      { year: null, month: "January", expected: 0 },
      { year: "", month: "January", expected: 0 },
      { year: 2023, month: "InvalidMonth", expected: 2023 * 12 + 0 }, // Defaults to 0
      { year: 2023, month: null, expected: 2023 * 12 + 0 }, // Defaults to 0
    ];

    it.each(testCases)(
      "should return score $expected for year: $year, month: $month",
      ({ year, month, expected }) => {
        expect(getDateScore(year, month)).toBe(expected);
      },
    );
  });

  describe("sortExperienceOrEducationList", () => {
    // Helper to create mock entries
    const createEntry = (id, isCurrent, startY, startM, endY, endM) => ({
      id,
      isCurrentlyWorking: isCurrent,
      startYear: startY,
      startMonth: startM,
      endYear: endY,
      endMonth: endM,
    });

    it("should prioritize currently working positions first", () => {
      const currentJob = createEntry(1, true, "2023", "January", "", "");
      const pastJob = createEntry(
        2,
        false,
        "2020",
        "January",
        "2022",
        "January",
      );

      const list = [pastJob, currentJob];
      const sorted = list.sort(sortExperienceOrEducationList);

      expect(sorted[0].id).toBe(1); // Current job first
      expect(sorted[1].id).toBe(2);
    });

    it("should sort by end date descending (newest end date first)", () => {
      const olderJob = createEntry(1, false, "2018", "Jan", "2019", "January");
      const newerJob = createEntry(2, false, "2020", "Jan", "2021", "January");

      const list = [olderJob, newerJob];
      const sorted = list.sort(sortExperienceOrEducationList);

      expect(sorted[0].id).toBe(2); // Ended in 2021
      expect(sorted[1].id).toBe(1); // Ended in 2019
    });

    it("should sort by start date descending if end dates are equal", () => {
      // Both ended in Dec 2022, but Job 2 started later (shorter duration, but more recent start)
      const jobStartedJan = createEntry(
        1,
        false,
        "2022",
        "January",
        "2022",
        "December",
      );
      const jobStartedJune = createEntry(
        2,
        false,
        "2022",
        "June",
        "2022",
        "December",
      );

      const list = [jobStartedJan, jobStartedJune];
      const sorted = list.sort(sortExperienceOrEducationList);

      expect(sorted[0].id).toBe(2); // Started June 2022 (Newer start)
      expect(sorted[1].id).toBe(1); // Started Jan 2022
    });

    it("should handle two currently working positions by sorting start date", () => {
      // Both are current, so end date score is 0 for both.
      // Comparison falls through to start date.
      const oldCurrentJob = createEntry(1, true, "2020", "January", "", "");
      const newCurrentJob = createEntry(2, true, "2023", "January", "", "");

      const list = [oldCurrentJob, newCurrentJob];
      const sorted = list.sort(sortExperienceOrEducationList);

      expect(sorted[0].id).toBe(2); // Started 2023 (Newest)
      expect(sorted[1].id).toBe(1); // Started 2020
    });

    it("should handle mixed scenarios correctly", () => {
      const itemA = createEntry("A", true, "2023", "January", "", ""); // Current
      const itemB = createEntry(
        "B",
        false,
        "2020",
        "January",
        "2022",
        "December",
      ); // Ended 2022
      const itemC = createEntry(
        "C",
        false,
        "2010",
        "January",
        "2012",
        "January",
      ); // Ended 2012
      const itemD = createEntry(
        "D",
        false,
        "2020",
        "January",
        "2022",
        "January",
      ); // Ended 2022 (Earlier month than B)

      const list = [itemC, itemA, itemD, itemB];
      const sorted = list.sort(sortExperienceOrEducationList);

      expect(sorted.map((i) => i.id)).toEqual(["A", "B", "D", "C"]);
    });
  });
});
