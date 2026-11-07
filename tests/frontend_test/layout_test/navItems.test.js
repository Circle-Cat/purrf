import { describe, test, expect } from "vitest";

import {
  NAV_GROUPS,
  isNavItemVisible,
  visibleNavItems,
} from "@/components/layout/navItems";
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

  test("gives every staff entry a tour sentence", () => {
    for (const group of NAV_GROUPS.filter(
      (g) => g.key !== "me" && g.key !== "apply",
    )) {
      for (const item of group.items) {
        expect(item.tourText).toMatch(new RegExp(`^${item.label} .+\\.$`));
      }
    }
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

describe("visibleNavItems", () => {
  test("returns the group's visible items in order", () => {
    const items = visibleNavItems("admin", {
      permissions: [PERMISSIONS.TRAINING_ADMIN_READ, PERMISSIONS.USER_ADMIN],
      flags: {},
    });

    expect(items.map((i) => i.label)).toEqual([
      "Accounts",
      "Training Administration",
    ]);
  });

  test("returns nothing for an unknown group", () => {
    expect(
      visibleNavItems("nope", {
        permissions: Object.values(PERMISSIONS),
        flags: {},
      }),
    ).toEqual([]);
  });
});
