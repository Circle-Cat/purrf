import { describe, test, expect, beforeEach } from "vitest";

import {
  RESET_KEY,
  autoStartCandidates,
  indexProgress,
  isResettableKey,
  isSeen,
  pageKey,
  qualifyingTasks,
} from "@/guides/progress";
import { markAutoStarted, resetGuideSession } from "@/guides/session";

const VIEWER = { permissions: [], flags: {}, mentorshipRoles: ["mentee"] };

const tour = (key, overrides = {}) => ({
  key,
  type: "tour",
  priority: 10,
  audience: () => true,
  trigger: { kind: "first-visit" },
  steps: [],
  ...overrides,
});

const TASK = {
  key: "task-alpha",
  type: "task",
  title: "Do alpha",
  priority: 5,
  audience: ({ mentorshipRoles }) => mentorshipRoles.length > 0,
  segments: [
    { key: "alpha-home", route: "/home", steps: [] },
    { key: "alpha-item", route: "/items/:itemId", steps: [] },
    { key: "alpha-home-more", route: "/home", steps: [] },
  ],
};

const keysOf = (candidates) =>
  candidates.map(({ guide, segment }) =>
    segment ? pageKey(segment) : guide.key,
  );

const at = (pathname) => ({ pathname });

describe("guide progress", () => {
  beforeEach(() => {
    resetGuideSession();
  });

  describe("indexProgress", () => {
    test("drops page and task rows written before the last reset", () => {
      const rows = [
        {
          guideKey: RESET_KEY,
          status: "completed",
          updatedAt: "2026-11-02T10:00:00Z",
        },
        {
          guideKey: "page-old",
          status: "completed",
          updatedAt: "2026-11-01T10:00:00Z",
        },
        {
          guideKey: "task-old",
          status: "completed",
          updatedAt: "2026-11-01T11:00:00Z",
        },
        {
          guideKey: "page-new",
          status: "dismissed",
          updatedAt: "2026-11-03T10:00:00Z",
        },
        {
          guideKey: "welcome",
          status: "completed",
          updatedAt: "2026-11-01T09:00:00Z",
        },
      ];

      const byKey = indexProgress(rows);

      expect([...byKey.keys()].sort()).toEqual([
        "page-new",
        "tour-reset",
        "welcome",
      ]);
      expect(byKey.get("page-new").status).toBe("dismissed");
    });

    test("keeps every row when there was no reset", () => {
      const rows = [
        {
          guideKey: "page-a",
          status: "snoozed",
          updatedAt: "2026-11-01T10:00:00Z",
        },
      ];

      expect(indexProgress(rows).get("page-a")).toBe(rows[0]);
    });
  });

  test("isResettableKey covers page and task keys only", () => {
    expect(isResettableKey("page-home")).toBe(true);
    expect(isResettableKey("task-alpha")).toBe(true);
    expect(isResettableKey("welcome")).toBe(false);
    expect(isResettableKey(RESET_KEY)).toBe(false);
  });

  test("isSeen holds for completed and dismissed rows only", () => {
    expect(isSeen({ status: "completed" })).toBe(true);
    expect(isSeen({ status: "dismissed" })).toBe(true);
    expect(isSeen({ status: "snoozed" })).toBe(false);
    expect(isSeen(undefined)).toBe(false);
  });

  test("qualifyingTasks keeps tasks whose audience includes the viewer", () => {
    const other = {
      ...TASK,
      key: "task-beta",
      priority: 9,
      audience: () => true,
    };
    const guides = [tour("welcome"), TASK, other];

    expect(qualifyingTasks(guides, VIEWER).map((t) => t.key)).toEqual([
      "task-beta",
      "task-alpha",
    ]);
    expect(
      qualifyingTasks(guides, { ...VIEWER, mentorshipRoles: [] }).map(
        (t) => t.key,
      ),
    ).toEqual(["task-beta"]);
  });

  describe("autoStartCandidates", () => {
    test("offers tours by priority, then the page's task segments", () => {
      const guides = [tour("low", { priority: 1 }), TASK, tour("high")];

      expect(
        keysOf(autoStartCandidates(guides, new Map(), VIEWER, at("/home"))),
      ).toEqual(["high", "low", "page-alpha-home", "page-alpha-home-more"]);
    });

    test("matches segment routes with params", () => {
      expect(
        keysOf(autoStartCandidates([TASK], new Map(), VIEWER, at("/items/7"))),
      ).toEqual(["page-alpha-item"]);
    });

    test.each([
      ["no row", undefined, true],
      ["a snoozed row", "snoozed", true],
      ["a completed row", "completed", false],
      ["a dismissed row", "dismissed", false],
    ])("a page intro with %s is offered: %s", (_label, status, offered) => {
      const progress = new Map(status ? [["page-alpha-home", { status }]] : []);

      expect(
        keysOf(autoStartCandidates([TASK], progress, VIEWER, at("/home"))),
      ).toEqual(
        offered
          ? ["page-alpha-home", "page-alpha-home-more"]
          : ["page-alpha-home-more"],
      );
    });

    test("offers no page intro of a completed task", () => {
      const progress = new Map([["task-alpha", { status: "completed" }]]);

      expect(
        autoStartCandidates([TASK], progress, VIEWER, at("/home")),
      ).toEqual([]);
    });

    test("offers page intros of a snoozed or dismissed task", () => {
      for (const status of ["snoozed", "dismissed"]) {
        const progress = new Map([["task-alpha", { status }]]);
        expect(
          autoStartCandidates([TASK], progress, VIEWER, at("/home")),
        ).toHaveLength(2);
      }
    });

    test("offers no page intro of a task outside the viewer's audience", () => {
      expect(
        autoStartCandidates(
          [TASK],
          new Map(),
          { ...VIEWER, mentorshipRoles: [] },
          at("/home"),
        ),
      ).toEqual([]);
    });

    test("leaves out what already started on its own this session", () => {
      markAutoStarted("welcome");
      markAutoStarted("page-alpha-home");

      expect(
        keysOf(
          autoStartCandidates(
            [tour("welcome"), TASK],
            new Map(),
            VIEWER,
            at("/home"),
          ),
        ),
      ).toEqual(["page-alpha-home-more"]);
    });

    test("respects a tour's row, audience, route and skipIf", () => {
      const guides = [
        tour("done"),
        tour("excluded", { audience: () => false }),
        tour("elsewhere", { route: "/other" }),
        tour("skipped", {
          trigger: {
            kind: "first-visit",
            skipIf: ({ pathname }) => pathname === "/home",
          },
        }),
        tour("manual-only", { trigger: undefined }),
        tour("here", { route: "/home" }),
      ];
      const progress = new Map([["done", { status: "completed" }]]);

      expect(
        keysOf(autoStartCandidates(guides, progress, VIEWER, at("/home"))),
      ).toEqual(["here"]);
    });

    test.each([
      ["no row", undefined, false],
      ["a snoozed row", "snoozed", false],
      ["a completed row", "completed", true],
      ["a dismissed row", "dismissed", true],
    ])(
      "a guide requiring one with %s is offered: %s",
      (_label, status, offered) => {
        const guides = [tour("feature", { requires: { seen: "welcome" } })];
        const progress = new Map(status ? [["welcome", { status }]] : []);

        expect(
          keysOf(autoStartCandidates(guides, progress, VIEWER, at("/home"))),
        ).toEqual(offered ? ["feature"] : []);
      },
    );
  });
});
