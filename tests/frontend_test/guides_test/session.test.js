import { describe, test, expect, beforeEach } from "vitest";

import {
  blockAutoStartOn,
  forgetAutoStarts,
  hasAutoStarted,
  isAutoStartBlocked,
  markAutoStarted,
  noteVisitedPath,
  resetGuideSession,
} from "@/guides/session";

describe("guide session", () => {
  beforeEach(() => {
    resetGuideSession();
  });

  test("starts with nothing auto-started and no page blocked", () => {
    expect(hasAutoStarted("welcome")).toBe(false);
    expect(isAutoStartBlocked("/start")).toBe(false);
  });

  test("remembers each auto-start by key until reset", () => {
    markAutoStarted("welcome");
    expect(hasAutoStarted("welcome")).toBe(true);
    expect(hasAutoStarted("page-home")).toBe(false);

    resetGuideSession();
    expect(hasAutoStarted("welcome")).toBe(false);
  });

  test("forgets only the auto-starts the predicate picks", () => {
    markAutoStarted("welcome");
    markAutoStarted("page-home");

    forgetAutoStarts((key) => key.startsWith("page-"));

    expect(hasAutoStarted("welcome")).toBe(true);
    expect(hasAutoStarted("page-home")).toBe(false);
  });

  test("blocks a page until the viewer is somewhere else", () => {
    blockAutoStartOn("/home");
    noteVisitedPath("/home");
    expect(isAutoStartBlocked("/home")).toBe(true);
    expect(isAutoStartBlocked("/other")).toBe(false);

    noteVisitedPath("/other");
    noteVisitedPath("/home");
    expect(isAutoStartBlocked("/home")).toBe(false);
  });
});
