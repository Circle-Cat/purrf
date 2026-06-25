import { describe, it, expect } from "vitest";
import { parseDates } from "@/lib/resume-parser/lib/dates";

describe("parseDates", () => {
  it("parses a month-year range", () => {
    expect(parseDates("Jan 2018 - Mar 2020")).toMatchObject({
      startDate: "2018-01-01",
      endDate: "2020-03-01",
      isCurrentJob: false,
    });
  });
  it("treats Present/Current (any case) as the current job", () => {
    expect(parseDates("2019 – PRESENT")).toMatchObject({
      startDate: "2019-01-01",
      endDate: null,
      isCurrentJob: true,
    });
    expect(parseDates("2021 to current")).toMatchObject({ isCurrentJob: true });
  });
  it("treats a single date as start only", () => {
    expect(parseDates("2022")).toMatchObject({
      startDate: "2022-01-01",
      endDate: null,
      isCurrentJob: false,
    });
  });
  it("swaps a reversed range and flags low confidence", () => {
    const r = parseDates("2022 - 2018");
    expect(r.startDate).toBe("2018-01-01");
    expect(r.endDate).toBe("2022-01-01");
    expect(r.lowConfidence).toBe(true);
  });
  it("returns empty (no throw) when no date is present", () => {
    expect(parseDates("no dates here")).toEqual({
      startDate: null,
      endDate: null,
      isCurrentJob: false,
      lowConfidence: false,
    });
  });
});
