import { describe, expect, it } from "vitest";
import { GUIDE_CHAPTERS } from "@/pages/WorkGuide/content";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

const SOURCES = import.meta.glob("@/**/*.{js,jsx}", {
  query: "?raw",
  import: "default",
  eager: true,
});

const allSource = Object.values(SOURCES).join("\n");
const appSource = Object.entries(SOURCES)
  .filter(([path]) => !path.includes("/pages/WorkGuide/"))
  .map(([, text]) => text)
  .join("\n");

// Bold text in the guide that emphasises a lead-in rather than naming a
// control, so it has no counterpart in the app's source.
const NOT_UI_LABELS = {
  "Where a reply goes.": "lead-in to a paragraph in How email works",
  "What Purrf emails by itself": "lead-in to a paragraph in How email works",
  "What Purrf does not email": "lead-in to a paragraph in How email works",
};

const flows = GUIDE_CHAPTERS.flatMap((chapter) => chapter.flows);
const steps = flows.flatMap((flow) =>
  flow.blocks.filter((b) => b.type === "steps").flatMap((b) => b.steps),
);

const textsOf = (flow) => [
  flow.title,
  flow.intro ?? "",
  ...flow.blocks.flatMap((block) => {
    switch (block.type) {
      case "text":
      case "heading":
        return [block.text];
      case "steps":
        return block.steps.map((step) => step.text);
      case "table":
        return [...block.columns, ...block.rows.flat()];
      case "goodToKnow":
        return block.items;
      default:
        return [];
    }
  }),
];

const boldLabels = () =>
  [
    ...new Set(
      flows
        .flatMap(textsOf)
        .flatMap((text) => [...text.matchAll(/\*\*(.+?)\*\*/g)])
        .map((match) => match[1]),
    ),
  ].sort();

const stripCount = (label) => label.replace(/(…| · N| \(n\))$/, "");

describe("GUIDE_CHAPTERS", () => {
  it("has the scanned sources to check against", () => {
    expect(Object.keys(SOURCES).length).toBeGreaterThan(50);
    expect(appSource).toContain("Send reply");
  });

  it("uses unique, URL-safe flow ids", () => {
    const ids = flows.map((flow) => flow.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const id of ids) expect(id).toMatch(/^[a-z0-9-]+$/);
  });

  it("only links steps to fixed app routes", () => {
    const routes = Object.values(ROUTE_PATHS).filter(
      (value) => typeof value === "string",
    );
    for (const step of steps.filter((s) => s.route)) {
      expect(routes).toContain(step.route);
    }
  });

  it("only highlights anchors that exist in the app", () => {
    for (const step of steps.filter((s) => s.anchor)) {
      expect(allSource).toContain(`data-whats-new="${step.anchor}"`);
    }
  });

  it("only bolds labels that appear in the app", () => {
    const labels = boldLabels();
    expect(labels.length).toBeGreaterThan(0);
    const missing = labels
      .filter((label) => !(label in NOT_UI_LABELS))
      .filter((label) => !appSource.includes(stripCount(label)));
    expect(missing).toEqual([]);
  });

  it("keeps the allow list to labels the guide still uses", () => {
    const labels = boldLabels();
    for (const label of Object.keys(NOT_UI_LABELS)) {
      expect(labels).toContain(label);
    }
  });
});
