import { describe, it, expect } from "vitest";
import { splitIntoSubsections } from "@/lib/resume-parser/lib/subsections";

const tok = (text, y, over = {}) => ({
  text,
  x: 60,
  y,
  width: text.length * 6,
  height: 11,
  fontName: "Helvetica",
  hasEOL: false,
  ...over,
});

describe("splitIntoSubsections", () => {
  it("splits on a vertical gap larger than 1.4x the typical line gap", () => {
    const lines = [
      [tok("Entry A line 1", 700)],
      [tok("Entry A line 2", 685)], // gap 15
      [tok("Entry B line 1", 650)], // gap 35 > 15*1.4
      [tok("Entry B line 2", 635)],
    ];
    expect(splitIntoSubsections(lines).length).toBe(2);
  });
  it("falls back to bold-turning-on when gaps are uniform", () => {
    const lines = [
      [tok("Company X", 700, { fontName: "Helvetica-Bold" })],
      [tok("did things", 685)],
      [tok("Company Y", 670, { fontName: "Helvetica-Bold" })],
      [tok("did more", 655)],
    ];
    expect(splitIntoSubsections(lines).length).toBe(2);
  });
});
