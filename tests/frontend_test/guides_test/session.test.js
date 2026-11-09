import { describe, test, expect, beforeEach } from "vitest";

import {
  hasAutoStarted,
  markAutoStarted,
  resetGuideSession,
} from "@/guides/session";

describe("guide session", () => {
  beforeEach(() => {
    resetGuideSession();
  });

  test("starts with no guide auto-started", () => {
    expect(hasAutoStarted()).toBe(false);
  });

  test("remembers an auto-start until reset", () => {
    markAutoStarted();
    expect(hasAutoStarted()).toBe(true);

    resetGuideSession();
    expect(hasAutoStarted()).toBe(false);
  });
});
