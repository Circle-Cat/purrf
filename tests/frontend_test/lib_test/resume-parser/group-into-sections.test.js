import { describe, it, expect } from "vitest";
import {
  groupIntoSections,
  isSectionTitle,
  lineText,
} from "@/lib/resume-parser/group-into-sections";

const tok = (text, over = {}) => ({
  text,
  x: 60,
  y: 700,
  width: text.length * 6,
  height: 11,
  fontName: "Helvetica",
  hasEOL: false,
  ...over,
});
const line = (...toks) => toks;

describe("isSectionTitle", () => {
  it("true for bold all-caps titles", () => {
    expect(
      isSectionTitle(line(tok("EXPERIENCE", { fontName: "Helvetica-Bold" }))),
    ).toBe(true);
  });
  it("true for keyword fallback titles", () => {
    expect(isSectionTitle(line(tok("Education")))).toBe(true);
  });
  it("false for multi-item lines and contact lines", () => {
    expect(isSectionTitle(line(tok("A"), tok("B")))).toBe(false);
    expect(isSectionTitle(line(tok("jane@example.com")))).toBe(false);
  });
});

describe("groupIntoSections", () => {
  it("isolates a one-line name then detects an immediate section title (header regression)", () => {
    const lines = [
      line(tok("Jane Doe", { fontName: "Helvetica-Bold" })),
      line(tok("EXPERIENCE", { fontName: "Helvetica-Bold" })),
      line(tok("Did things")),
    ];
    const sections = groupIntoSections(lines);
    expect(lineText(sections.profile[0])).toBe("Jane Doe");
    expect(sections.EXPERIENCE).toBeDefined();
    expect(lineText(sections.EXPERIENCE[0])).toBe("Did things");
  });
  it("keeps a contact line in the header but stops at the first non-contact line", () => {
    const lines = [
      line(tok("Jane Doe", { fontName: "Helvetica-Bold" })),
      line(tok("jane@example.com")),
      line(tok("SKILLS", { fontName: "Helvetica-Bold" })),
    ];
    const sections = groupIntoSections(lines);
    expect(sections.profile.length).toBe(2);
    expect(sections.SKILLS).toBeDefined();
  });
});
