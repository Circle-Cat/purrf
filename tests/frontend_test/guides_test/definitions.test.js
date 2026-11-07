import { describe, test, expect } from "vitest";

import { GUIDES } from "@/guides/definitions";
import { NAV_GROUPS } from "@/components/layout/navItems";

const welcome = GUIDES.find((guide) => guide.key === "welcome");

describe("GUIDES", () => {
  test("keeps the welcome tour under its stored key", () => {
    expect(welcome).toBeDefined();
    expect(welcome.type).toBe("tour");
    expect(welcome.trigger).toEqual({ kind: "first-visit" });
  });

  test("walks the avatar menu, then each sidebar group, then closes", () => {
    expect(welcome.steps.map(({ anchor, title }) => [anchor, title])).toEqual([
      ["avatar-menu", "Your account menu"],
      ["nav-group-me", "Your home page"],
      ["nav-group-apply", "Open Positions"],
      ["nav-group-recruiting", "Recruiting"],
      ["nav-group-mentorship", "Mentorship"],
      ["nav-group-activity", "Activity data"],
      ["nav-group-admin", "Administration"],
      ["avatar-menu", "That's it for now"],
    ]);
  });

  test("expands the sidebar before every sidebar step and no other", () => {
    expect(welcome.steps.map((step) => step.before ?? null)).toEqual([
      null,
      "expand-sidebar",
      "expand-sidebar",
      "expand-sidebar",
      "expand-sidebar",
      "expand-sidebar",
      "expand-sidebar",
      null,
    ]);
  });

  test("builds the body of each staff group step from that group", () => {
    const built = welcome.steps.filter((step) => step.navGroup);

    expect(built.map((step) => step.navGroup)).toEqual([
      "recruiting",
      "mentorship",
      "activity",
      "admin",
    ]);
    for (const step of built) {
      expect(step.anchor).toBe(`nav-group-${step.navGroup}`);
      expect(step.body).toBeUndefined();
      expect(NAV_GROUPS.some((group) => group.key === step.navGroup)).toBe(
        true,
      );
    }
  });

  test("gives every other step a fixed body", () => {
    for (const step of welcome.steps.filter((s) => !s.navGroup)) {
      expect(typeof step.body).toBe("string");
      expect(step.body.length).toBeGreaterThan(0);
    }
  });
});
