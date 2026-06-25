import { describe, it, expect } from "vitest";
import { extractWork } from "@/lib/resume-parser/extract-work";

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

describe("extractWork", () => {
  it("extracts title, company, and a current-job range", () => {
    const lines = [
      [tok("Senior Engineer", 700, { fontName: "Helvetica-Bold" })],
      [tok("Acme Corp", 685, { fontName: "Helvetica-Bold" })],
      [tok("Jan 2020 - Present", 670)],
      [tok("• Built things", 655)],
    ];
    const [job] = extractWork(lines);
    expect(job.title).toMatch(/Senior Engineer/);
    expect(job.companyOrOrganization).toMatch(/Acme Corp/);
    expect(job.isCurrentJob).toBe(true);
    expect(job.endDate).toBeNull();
  });
});
