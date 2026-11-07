import { describe, test, expect } from "vitest";

import { resolveSteps } from "@/guides/steps";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { PERMISSIONS } from "@/constants/Permissions";

const STEPS = [
  { anchor: "avatar-menu", title: "Fixed", body: "Fixed body" },
  {
    anchor: "nav-group-recruiting",
    title: "Recruiting",
    navGroup: "recruiting",
  },
  { anchor: "nav-group-admin", title: "Administration", navGroup: "admin" },
  { anchor: "nav-group-activity", title: "Activity", navGroup: "activity" },
];

describe("resolveSteps", () => {
  test("lists only the entries the viewer sees, in sidebar order", () => {
    const steps = resolveSteps(STEPS, {
      permissions: [
        PERMISSIONS.RECRUITING_AUDIT_READ,
        PERMISSIONS.RECRUITING_JOB_READ,
        PERMISSIONS.PERMISSION_MANAGE,
      ],
      flags: {},
    });

    expect(steps.map((step) => step.title)).toEqual([
      "Fixed",
      "Recruiting",
      "Administration",
    ]);
    expect(steps[1].body).toEqual([
      "Job Postings is where postings are drafted, reviewed and published.",
      "Recruiting Audit reports on applications across postings.",
    ]);
    expect(steps[2].body).toEqual([
      "User Permissions grants and removes permissions.",
    ]);
  });

  test("passes a fixed step through untouched", () => {
    const [fixed] = resolveSteps(STEPS, { permissions: [], flags: {} });

    expect(fixed).toBe(STEPS[0]);
  });

  test("drops a step whose group the viewer sees nothing of", () => {
    const steps = resolveSteps(STEPS, {
      permissions: [PERMISSIONS.INTERNAL_ACTIVITY_READ],
      flags: {},
    });

    expect(steps.map((step) => step.title)).toEqual(["Fixed", "Activity"]);
    expect(steps[1].body).toEqual([
      "DataSearch looks up work activity by person and date.",
    ]);
  });

  test("counts an entry behind a flag only while the flag is on", () => {
    const viewer = { permissions: [PERMISSIONS.LEAVE_ADMIN] };

    expect(
      resolveSteps(STEPS, { ...viewer, flags: {} }).map((s) => s.title),
    ).toEqual(["Fixed"]);
    expect(
      resolveSteps(STEPS, {
        ...viewer,
        flags: { [FEATURE_FLAGS.LEAVE_MANAGEMENT]: true },
      })[1].body,
    ).toEqual([
      "Leave Administration manages company holidays and everyone's leave balances.",
    ]);
  });

  test("drops a step naming a group that does not exist", () => {
    const steps = resolveSteps(
      [{ anchor: "x", title: "Unknown", navGroup: "nope" }],
      { permissions: Object.values(PERMISSIONS), flags: {} },
    );

    expect(steps).toEqual([]);
  });
});
