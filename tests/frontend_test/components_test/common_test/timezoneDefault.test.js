import { describe, it, expect, vi, afterEach } from "vitest";

import {
  supportedTimezone,
  browserTimezone,
} from "@/components/common/timezoneDefault";

// Fixed, and in northern winter, so a rule about offsets is decided by the
// argument and not by whether the suite runs during someone's DST.
const WINTER = new Date("2026-01-15T12:00:00Z");

/** Minutes east of UTC that `zone` is on at `WINTER`. */
const offsetAt = (zone) => {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: zone,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).formatToParts(WINTER);
  const at = Object.fromEntries(parts.map((p) => [p.type, p.value]));
  const asUtc = Date.UTC(
    Number(at.year),
    Number(at.month) - 1,
    Number(at.day),
    Number(at.hour) % 24,
    Number(at.minute),
  );
  return Math.round((asUtc - WINTER.getTime()) / 60000);
};

describe("supportedTimezone", () => {
  it("keeps a zone the picker offers by name", () => {
    expect(supportedTimezone("America/New_York", WINTER)).toBe(
      "America/New_York",
    );
    expect(supportedTimezone("Asia/Shanghai", WINTER)).toBe("Asia/Shanghai");
  });

  it("maps a zone the picker lacks onto a listed one at the same offset", () => {
    // The list is a curated ~26 entries, not the IANA database. Taipei is not
    // on it; Shanghai is, at the same +8.
    expect(supportedTimezone("Asia/Taipei", WINTER)).toBe("Asia/Shanghai");
    expect(supportedTimezone("Asia/Manila", WINTER)).toBe("Asia/Shanghai");
  });

  it("maps a legacy alias onto the name the picker uses", () => {
    // A browser may still report the pre-1993 spelling.
    expect(supportedTimezone("Asia/Calcutta", WINTER)).toBe("Asia/Kolkata");
  });

  it("will cross regions to match an offset", () => {
    // Guam is +10; the Pacific entries are Honolulu (-10) and Auckland (+13),
    // so the match has to come from Australia.
    const mapped = supportedTimezone("Pacific/Guam", WINTER);
    expect(mapped).not.toBe("");
    expect(offsetAt(mapped)).toBe(offsetAt("Pacific/Guam"));
  });

  it("gives up rather than guess when no entry shares the offset", () => {
    // Nothing on the list sits at +5:45.
    expect(supportedTimezone("Asia/Kathmandu", WINTER)).toBe("");
  });

  it("gives up on nothing at all", () => {
    expect(supportedTimezone(undefined, WINTER)).toBe("");
    expect(supportedTimezone("", WINTER)).toBe("");
  });

  it("gives up on a zone name no engine recognises", () => {
    expect(supportedTimezone("Mars/Olympus_Mons", WINTER)).toBe("");
  });

  it("does not treat an inherited Object property as a zone", () => {
    expect(supportedTimezone("constructor", WINTER)).toBe("");
    expect(supportedTimezone("toString", WINTER)).toBe("");
  });
});

describe("browserTimezone", () => {
  afterEach(() => vi.restoreAllMocks());

  it("maps the environment's own zone through the same rule", () => {
    const real = Intl.DateTimeFormat;
    vi.spyOn(Intl, "DateTimeFormat").mockImplementation((...args) =>
      args.length
        ? new real(...args)
        : { resolvedOptions: () => ({ timeZone: "Asia/Taipei" }) },
    );
    expect(browserTimezone(WINTER)).toBe("Asia/Shanghai");
  });

  it("reports nothing rather than throwing when the environment has no answer", () => {
    vi.spyOn(Intl, "DateTimeFormat").mockImplementation(() => {
      throw new Error("no ICU data");
    });
    expect(browserTimezone(WINTER)).toBe("");
  });
});
