import { describe, it, expect } from "vitest";

import {
  assignBlockedReason,
  canAssign,
  liveStateLabel,
  publishBlockedReason,
  timeSpentLabel,
} from "@/pages/AdminTraining/utils";

const live = { liveState: "live", isActive: true };

describe("liveStateLabel", () => {
  it("labels every live state the backend derives", () => {
    expect(liveStateLabel("live")).toBe("Live");
    expect(liveStateLabel("no_package")).toBe("No package");
    expect(liveStateLabel("external_link")).toBe("External link");
  });
});

describe("canAssign", () => {
  it("allows a live course that is active", () => {
    expect(canAssign({ liveState: "live", isActive: true })).toBe(true);
  });

  it("refuses a course whose only package is staged", () => {
    expect(
      canAssign({
        liveState: "no_package",
        isActive: true,
        staged: { packageId: 2 },
      }),
    ).toBe(false);
  });

  it("refuses a deactivated course, which the API answers 409 for", () => {
    // Both halves of the backend gate, or the still-enabled button sends the
    // admin through the whole assign form to reach a rejection.
    expect(canAssign({ ...live, isActive: false })).toBe(false);
  });
});

describe("assignBlockedReason", () => {
  it("says nothing about a course that can be assigned", () => {
    expect(assignBlockedReason(live)).toBeNull();
  });

  it("names publishing a package when the course has none live", () => {
    expect(assignBlockedReason({ ...live, liveState: "no_package" })).toBe(
      "Publish a package to this course first",
    );
  });

  it("names turning the course back on when that is what is missing", () => {
    // Two rules, two sentences: they need different actions from the admin.
    expect(assignBlockedReason({ ...live, isActive: false })).toBe(
      "This course is deactivated. Turn it back on to assign it.",
    );
  });
});

describe("publishBlockedReason", () => {
  it("says there is nothing staged when there is no staged package", () => {
    expect(publishBlockedReason({ staged: null })).toBe(
      "There is nothing staged to publish",
    );
  });

  it("names the missing trial run when the staged package is unverified", () => {
    const course = { staged: { packageId: 2, verifiedCompletableAt: null } };

    expect(publishBlockedReason(course)).toBe(
      "Run this package to completion first",
    );
  });

  it("clears once the staged package carries a stamp", () => {
    const course = {
      staged: { packageId: 2, verifiedCompletableAt: "2026-09-05T03:41:00Z" },
    };

    expect(publishBlockedReason(course)).toBeNull();
  });
});

describe("timeSpentLabel", () => {
  it("reads an em dash for an assignment nobody opened", () => {
    expect(timeSpentLabel(null)).toBe("—");
    expect(timeSpentLabel(undefined)).toBe("—");
  });

  it("reads seconds under a minute", () => {
    expect(timeSpentLabel(45)).toBe("45s");
  });

  it("reads minutes and seconds under an hour", () => {
    expect(timeSpentLabel(940)).toBe("15m 40s");
  });

  it("reads hours and minutes above one", () => {
    expect(timeSpentLabel(7325)).toBe("2h 2m");
  });

  it("reads zero as zero rather than as never opened", () => {
    expect(timeSpentLabel(0)).toBe("0s");
  });
});
