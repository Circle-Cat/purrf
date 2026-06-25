import { describe, it, expect } from "vitest";
import {
  extractEducation,
  extractFieldOfStudy,
} from "@/lib/resume-parser/extract-education";

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

describe("extractFieldOfStudy", () => {
  it("pulls the field after 'in' and trims trailing noise", () => {
    expect(
      extractFieldOfStudy("Bachelor of Science in Computer Science, 2020"),
    ).toBe("Computer Science");
    expect(extractFieldOfStudy("B.S. in Mathematics 3.8 GPA")).toBe(
      "Mathematics",
    );
  });
  it("returns '' when no field is found", () => {
    expect(extractFieldOfStudy("Bachelor of Science")).toBe("");
  });
  it("handles a glued separator and strips a (GPA) parenthetical", () => {
    expect(
      extractFieldOfStudy("Bachelor of Arts inComputer Science(GPA:4.0/4.0)"),
    ).toBe("Computer Science");
  });
  it("reads a field stated before the degree abbreviation", () => {
    expect(extractFieldOfStudy("Mathematics BSc")).toBe("Mathematics");
    expect(extractFieldOfStudy("Data Science MSc")).toBe("Data Science");
  });
});

describe("extractEducation", () => {
  it("extracts school, degree, and dates for one entry", () => {
    const lines = [
      [tok("Stanford University", 700, { fontName: "Helvetica-Bold" })],
      [tok("Bachelor of Science in Computer Science", 685)],
      [tok("2016 - 2020", 670)],
    ];
    const [entry] = extractEducation(lines);
    expect(entry.school).toMatch(/Stanford University/);
    expect(entry.degree).toMatch(/Bachelor/);
    expect(entry.fieldOfStudy).toBe("Computer Science");
    expect(entry.startDate).toBe("2016-01-01");
  });

  it("keeps the school when school, degree and GPA share one line", () => {
    const lines = [
      [
        tok("Northeastern University (GPA 3.92)", 700),
        tok("Master of Computer Software Engineering", 700, { x: 300 }),
        tok("Sep 2024–Dec 2026", 700, { x: 520 }),
      ],
    ];
    const [entry] = extractEducation(lines);
    expect(entry.school).toBe("Northeastern University");
    expect(entry.degree).toMatch(/Master/);
  });
});
