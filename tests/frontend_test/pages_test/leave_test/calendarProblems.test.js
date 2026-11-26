import { describe, it, expect } from "vitest";

import { calendarProblems } from "@/pages/Leave/utils/calendarProblems";

const holiday = (name, startDate, endDate = startDate) => ({
  name,
  startDate,
  endDate,
  isExchangeable: false,
});

describe("calendarProblems", () => {
  it("finds nothing wrong with a well-formed year", () => {
    const result = calendarProblems(2026, [
      holiday("New Year", "2026-01-01"),
      holiday("National Day", "2026-10-01", "2026-10-07"),
    ]);

    expect(result).toEqual({ byIndex: {}, hasProblems: false });
  });

  it("refuses to save an empty year", () => {
    expect(calendarProblems(2026, []).hasProblems).toBe(true);
  });

  it("says one thing about a row just added", () => {
    const { byIndex } = calendarProblems(2026, [holiday("", "")]);

    expect(byIndex[0]).toEqual(["Fill in this holiday, or remove it."]);
  });

  it("asks for a name", () => {
    const { byIndex } = calendarProblems(2026, [holiday("  ", "2026-01-01")]);

    expect(byIndex[0]).toEqual(["Give the holiday a name."]);
  });

  it("asks for both days", () => {
    const { byIndex } = calendarProblems(2026, [
      holiday("New Year", "2026-01-01", ""),
    ]);

    expect(byIndex[0]).toEqual(["Give its first and last day."]);
  });

  it("marks a holiday that ends before it starts", () => {
    const { byIndex } = calendarProblems(2026, [
      holiday("New Year", "2026-01-03", "2026-01-01"),
    ]);

    expect(byIndex[0]).toEqual(["It ends before it starts."]);
  });

  it("marks a holiday that spans two years", () => {
    const { byIndex } = calendarProblems(2026, [
      holiday("New Year", "2026-12-31", "2027-01-01"),
    ]);

    expect(byIndex[0]).toEqual([
      "It spans two years. Enter it as two holidays, one per year.",
    ]);
  });

  it("marks a holiday in another year", () => {
    const { byIndex } = calendarProblems(2026, [
      holiday("New Year", "2027-01-01"),
    ]);

    expect(byIndex[0]).toEqual(["It falls in 2027, not 2026."]);
  });

  it("marks both holidays that cover the same day, naming the day", () => {
    const { byIndex } = calendarProblems(2026, [
      holiday("National Day", "2026-10-01", "2026-10-07"),
      holiday("Mid-Autumn", "2026-10-05"),
      holiday("New Year", "2026-01-01"),
    ]);

    expect(byIndex[0]).toEqual(["It overlaps Mid-Autumn on Oct 5, 2026."]);
    expect(byIndex[1]).toEqual(["It overlaps National Day on Oct 5, 2026."]);
    expect(byIndex[2]).toBeUndefined();
  });

  it("does not report an overlap against a row that is itself broken", () => {
    const { byIndex } = calendarProblems(2026, [
      holiday("National Day", "2026-10-07", "2026-10-01"),
      holiday("Mid-Autumn", "2026-10-05"),
    ]);

    expect(byIndex[0]).toEqual(["It ends before it starts."]);
    expect(byIndex[1]).toBeUndefined();
  });
});
