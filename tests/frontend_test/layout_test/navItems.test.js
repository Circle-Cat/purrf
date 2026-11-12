import { describe, test, expect } from "vitest";

import { NAV_GROUPS, isNavItemVisible } from "@/components/layout/navItems";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { PERMISSIONS } from "@/constants/Permissions";

describe("NAV_GROUPS", () => {
  test("orders the groups as the sidebar shows them", () => {
    expect(NAV_GROUPS.map((group) => group.key)).toEqual([
      "me",
      "apply",
      "recruiting",
      "mentorship",
      "activity",
      "admin",
    ]);
  });
});

describe("isNavItemVisible", () => {
  const item = {
    permissions: [PERMISSIONS.RECRUITING_JOB_READ, PERMISSIONS.USER_ADMIN],
  };

  test("shows an open item to anyone", () => {
    expect(
      isNavItemVisible({ permissions: [] }, { permissions: [], flags: {} }),
    ).toBe(true);
  });

  test("needs any one of the listed permissions", () => {
    expect(
      isNavItemVisible(item, {
        permissions: [PERMISSIONS.USER_ADMIN],
        flags: {},
      }),
    ).toBe(true);
    expect(
      isNavItemVisible(item, {
        permissions: [PERMISSIONS.LEAVE_ADMIN, PERMISSIONS.PERMISSION_MANAGE],
        flags: {},
      }),
    ).toBe(false);
  });

  test("also needs the item's flag on", () => {
    const flagged = { ...item, flag: FEATURE_FLAGS.LEAVE_MANAGEMENT };
    const viewer = { permissions: [PERMISSIONS.RECRUITING_JOB_READ] };

    expect(isNavItemVisible(flagged, { ...viewer, flags: {} })).toBe(false);
    expect(
      isNavItemVisible(flagged, {
        ...viewer,
        flags: { [FEATURE_FLAGS.LEAVE_MANAGEMENT]: true },
      }),
    ).toBe(true);
  });
});
