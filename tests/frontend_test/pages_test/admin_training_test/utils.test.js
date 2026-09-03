import { describe, it, expect } from "vitest";

import {
  assignBlockedReason,
  canAssign,
  statusLabel,
} from "@/pages/AdminTraining/utils";

const verified = { state: "verified", isActive: true };

describe("statusLabel", () => {
  it("labels every state the backend derives", () => {
    expect(statusLabel("verified")).toBe("Verified");
    expect(statusLabel("needs_trial_run")).toBe("Needs trial run");
    expect(statusLabel("no_package")).toBe("No package");
    expect(statusLabel("external_link")).toBe("External link");
  });
});

describe("canAssign", () => {
  it("allows a verified, active course", () => {
    expect(canAssign(verified)).toBe(true);
  });

  it("refuses a course nobody has run to completion", () => {
    expect(canAssign({ ...verified, state: "needs_trial_run" })).toBe(false);
  });

  it("refuses a deactivated course, which the API answers 409 for", () => {
    // Both halves of the backend gate, or the still-enabled button sends the
    // admin through the whole assign form to reach a rejection.
    expect(canAssign({ ...verified, isActive: false })).toBe(false);
  });
});

describe("assignBlockedReason", () => {
  it("says nothing about a course that can be assigned", () => {
    expect(assignBlockedReason(verified)).toBeNull();
  });

  it("names running the course when that is what is missing", () => {
    expect(assignBlockedReason({ ...verified, state: "needs_trial_run" })).toBe(
      "Run this course to completion first",
    );
  });

  it("names turning the course back on when that is what is missing", () => {
    // Two rules, two sentences: they need different actions from the admin.
    expect(assignBlockedReason({ ...verified, isActive: false })).toBe(
      "This course is deactivated. Turn it back on to assign it.",
    );
  });
});
