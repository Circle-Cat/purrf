import { describe, it, expect } from "vitest";
import {
  inferTimezone,
  normalizeState,
} from "@/lib/resume-parser/lib/timezone";

describe("normalizeState", () => {
  it("maps a 2-letter code and a full name to a code", () => {
    expect(normalizeState("CA")).toBe("CA");
    expect(normalizeState("California")).toBe("CA");
    expect(normalizeState("Nowhere")).toBeNull();
  });
});

describe("inferTimezone", () => {
  it("maps a state code to its IANA zone", () => {
    expect(inferTimezone("San Francisco, CA")).toBe("America/Los_Angeles");
    expect(inferTimezone("Houston, Texas")).toBe("America/Chicago");
  });
  it("a city override wins over the state table (split-zone)", () => {
    expect(inferTimezone("El Paso, TX")).toBe("America/Denver");
  });
  it("returns null when the state is missing/unknown", () => {
    expect(inferTimezone("Just A City")).toBeNull();
  });
});
