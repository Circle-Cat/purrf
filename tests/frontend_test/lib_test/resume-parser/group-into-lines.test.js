import { describe, it, expect } from "vitest";
import {
  groupIntoLines,
  typicalCharWidth,
} from "@/lib/resume-parser/group-into-lines";

const it_ = (text, x, over = {}) => ({
  text,
  x,
  y: 700,
  width: text.length * 6,
  height: 11,
  fontName: "Helvetica",
  hasEOL: false,
  ...over,
});

describe("groupIntoLines", () => {
  it("splits on hasEOL", () => {
    const items = [it_("A", 60, { hasEOL: true }), it_("B", 60)];
    const lines = groupIntoLines(items);
    expect(lines.length).toBe(2);
  });
  it("merges adjacent fragments into one item", () => {
    const items = [it_("Soft", 60), it_("ware", 60 + 4 * 6, { hasEOL: true })];
    const lines = groupIntoLines(items);
    expect(lines[0].map((i) => i.text).join("")).toBe("Software");
  });
  it("re-inserts a space after punctuation when merging", () => {
    const items = [
      it_("Skills:", 60),
      it_("Python", 60 + 7 * 6, { hasEOL: true }),
    ];
    const lines = groupIntoLines(items);
    expect(lines[0][0].text).toBe("Skills: Python");
  });
});

describe("typicalCharWidth", () => {
  it("falls back to the global median when the top pair has < 3 samples", () => {
    const items = [
      it_("ab", 0),
      it_("cd", 0, { height: 22 }),
      it_("ef", 0, { height: 33 }),
    ];
    expect(typicalCharWidth(items)).toBeGreaterThan(0);
  });
  it("clamps an absurd width back into range", () => {
    const items = [
      it_("x", 0, { width: 999 }),
      it_("y", 0, { width: 999 }),
      it_("z", 0, { width: 999 }),
    ];
    const w = typicalCharWidth(items);
    expect(w).toBeLessThanOrEqual(20);
    expect(w).toBeGreaterThanOrEqual(3);
  });
});
