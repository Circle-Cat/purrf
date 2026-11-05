import { describe, it, expect } from "vitest";
import {
  isWithinJoinWindow,
  JOIN_GRACE_MS,
} from "@/utils/meetingStatusCalculator";

// A fixed instant, so nothing here depends on the wall clock.
const NOW = new Date("2026-03-01T12:00:00Z").getTime();
const at = (offsetMs) => new Date(NOW + offsetMs).toISOString();

describe("isWithinJoinWindow", () => {
  it("should accept a meeting that has not started yet", () => {
    expect(isWithinJoinWindow(at(2 * 60 * 60 * 1000), NOW)).toBe(true);
  });

  it("should accept a meeting that is still running", () => {
    expect(isWithinJoinWindow(at(10 * 60 * 1000), NOW)).toBe(true);
  });

  it("should accept a meeting that ended less than the grace period ago", () => {
    expect(isWithinJoinWindow(at(-(JOIN_GRACE_MS / 2)), NOW)).toBe(true);
  });

  it("should reject a meeting whose grace period has elapsed", () => {
    expect(isWithinJoinWindow(at(-JOIN_GRACE_MS - 1000), NOW)).toBe(false);
  });

  it("should reject a meeting that ended long ago", () => {
    expect(isWithinJoinWindow(at(-30 * 24 * 60 * 60 * 1000), NOW)).toBe(false);
  });

  it("should reject rather than accept when the end time is missing or unparseable", () => {
    // NaN comparisons are false, which lands on hiding the entry point --
    // the safe direction for a bad or absent timestamp.
    expect(isWithinJoinWindow(undefined, NOW)).toBe(false);
    expect(isWithinJoinWindow("not a date", NOW)).toBe(false);
  });
});
