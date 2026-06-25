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

  it('splits "Company | Title" sharing one line with a right-aligned date', () => {
    const lines = [
      [
        tok("Alice Cabinetry | Full-stack Developer", 700),
        tok("Jan 2026 - Present", 700, { x: 400 }),
      ],
      [tok("• Built the site", 685)],
    ];
    const [job] = extractWork(lines);
    expect(job.title).toBe("Full-stack Developer");
    expect(job.companyOrOrganization).toBe("Alice Cabinetry");
    expect(job.isCurrentJob).toBe(true);
  });

  it("picks the job-title line as title and the other line as company", () => {
    const lines = [
      [tok("Recreational Sports & Wellbeing, Big University", 700)],
      [
        tok("Intramural Soccer Official", 685),
        tok("Jan 2026 - Present", 685, { x: 400 }),
      ],
      [tok("• Officiated matches", 670)],
    ];
    const [job] = extractWork(lines);
    expect(job.title).toBe("Intramural Soccer Official");
    expect(job.companyOrOrganization).toMatch(/Recreational Sports/);
  });
});
