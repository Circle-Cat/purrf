import { describe, it, expect } from "vitest";
import {
  DURATION_OPTIONS,
  DEFAULT_DURATION_MINUTES,
  durationFromRange,
} from "@/utils/meetingSlot";

describe("meetingSlot", () => {
  it("offers exactly the durations the backend accepts", () => {
    expect(DURATION_OPTIONS.map((o) => Number(o.value))).toEqual([
      30, 45, 60, 90,
    ]);
  });

  it("defaults to a duration that is one of the options", () => {
    expect(DURATION_OPTIONS.map((o) => Number(o.value))).toContain(
      DEFAULT_DURATION_MINUTES,
    );
  });

  it("recovers each offered duration from a matching range", () => {
    expect(
      durationFromRange("2026-04-01T10:00:00Z", "2026-04-01T10:30:00Z"),
    ).toBe(30);
    expect(
      durationFromRange("2026-04-01T10:00:00Z", "2026-04-01T11:30:00Z"),
    ).toBe(90);
  });

  it("falls back to the default for a range the select cannot show", () => {
    // 25 minutes is not an option; returning it would render a Select with
    // no matching item and an empty trigger.
    expect(
      durationFromRange("2026-04-01T10:00:00Z", "2026-04-01T10:25:00Z"),
    ).toBe(DEFAULT_DURATION_MINUTES);
  });

  it("falls back to the default when either end is missing or unparsable", () => {
    expect(durationFromRange(undefined, undefined)).toBe(
      DEFAULT_DURATION_MINUTES,
    );
    expect(durationFromRange("not a date", "2026-04-01T10:30:00Z")).toBe(
      DEFAULT_DURATION_MINUTES,
    );
  });
});
