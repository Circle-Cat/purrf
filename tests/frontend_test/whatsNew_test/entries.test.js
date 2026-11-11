import { describe, test, expect } from "vitest";
import { WHATS_NEW_ENTRIES } from "@/whatsNew/entries";
import { whatsNewEntryKey } from "@/whatsNew/progressKeys";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";

describe("WHATS_NEW_ENTRIES", () => {
  test("ids are unique slugs that make valid progress keys", () => {
    const ids = WHATS_NEW_ENTRIES.map((entry) => entry.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) {
      expect(id).toMatch(/^[a-z0-9-]{1,50}$/);
      expect(id).not.toBe("intro");
      // The backend accepts 1 to 64 lowercase letters, digits or hyphens.
      expect(whatsNewEntryKey(id)).toMatch(/^[a-z0-9-]{1,64}$/);
    }
  });

  test("undated entries come first, dated ones newest first, all short", () => {
    const firstDated = WHATS_NEW_ENTRIES.findIndex((entry) => entry.date);
    const dated = firstDated === -1 ? [] : WHATS_NEW_ENTRIES.slice(firstDated);
    for (const entry of dated) expect(entry.date).toBeDefined();
    const dates = dated.map((entry) => entry.date);
    for (const entry of WHATS_NEW_ENTRIES) {
      if (entry.date !== undefined) {
        expect(entry.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(Number.isNaN(Date.parse(entry.date))).toBe(false);
      }
      expect(entry.title.length).toBeLessThanOrEqual(40);
      expect(entry.body.length).toBeGreaterThan(0);
      if (entry.audience !== undefined) {
        expect(typeof entry.audience).toBe("function");
      }
    }
    expect([...dates].sort().reverse()).toEqual(dates);
  });

  test("a flag, when given, is a known LaunchDarkly flag", () => {
    const known = Object.values(FEATURE_FLAGS);
    for (const entry of WHATS_NEW_ENTRIES) {
      if (entry.flag !== undefined) expect(known).toContain(entry.flag);
    }
  });

  test("every Show me link names a known route and an anchor", () => {
    const routes = Object.values(ROUTE_PATHS);
    for (const entry of WHATS_NEW_ENTRIES) {
      expect(routes).toContain(entry.showMe.route);
      expect(entry.showMe.anchor).toMatch(/^[a-z0-9-]+$/);
    }
  });

  test("the multiple-email sign-in entry reaches everyone and points at Add email", () => {
    const entry = WHATS_NEW_ENTRIES.find(
      (e) => e.id === "sign-in-with-any-email",
    );
    expect(entry.showMe).toEqual({
      route: ROUTE_PATHS.SIGN_IN_SECURITY,
      anchor: "add-email",
    });
    expect(entry.flag).toBeUndefined();
    expect(entry.audience).toBeUndefined();
  });
});
