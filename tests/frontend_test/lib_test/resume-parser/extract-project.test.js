import { describe, it, expect } from "vitest";
import { extractProjects } from "@/lib/resume-parser/extract-project";

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

describe("extractProjects", () => {
  it("pulls one entry per subsection: name (date stripped) + dates", () => {
    const lines = [
      [
        tok("DocuMind: RAG Prototype", 700, { fontName: "Helvetica-Bold" }),
        tok("Apr 2025 - Jun 2025", 700, { x: 400 }),
      ],
      [tok("• Built a pipeline", 685)],
      [
        tok("Kernel Benchmark", 650, { fontName: "Helvetica-Bold" }),
        tok("Jan 2026 - May 2026", 650, { x: 400 }),
      ],
      [tok("• Benchmarked LLMs", 635)],
    ];
    const projects = extractProjects(lines);
    expect(projects).toHaveLength(2);
    expect(projects[0].name).toBe("DocuMind: RAG Prototype");
    expect(projects[0].startDate).toBe("2025-04-01");
    expect(projects[1].name).toBe("Kernel Benchmark");
  });

  it("returns [] for empty input", () => {
    expect(extractProjects([])).toEqual([]);
  });
});
