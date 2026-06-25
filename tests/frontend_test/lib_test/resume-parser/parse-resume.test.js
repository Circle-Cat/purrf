import { describe, it, expect } from "vitest";
import { parseResumeFromPdf } from "@/lib/resume-parser";
import { makeResumePdf } from "./resume.helper";

describe("parseResumeFromPdf (integration)", () => {
  it("parses a small resume end-to-end", async () => {
    const bytes = await makeResumePdf([
      [{ text: "Jane Doe", bold: true, size: 16 }],
      [{ text: "jane@example.com" }],
      [{ text: "San Francisco, CA" }],
      [{ text: "linkedin.com/in/janedoe" }],
      [{ text: "EXPERIENCE", bold: true }],
      [{ text: "Senior Engineer", bold: true }],
      [{ text: "Acme Corp", bold: true }],
      [{ text: "Jan 2020 - Present" }],
      [{ text: "EDUCATION", bold: true }],
      [{ text: "Stanford University", bold: true }],
      [{ text: "Bachelor of Science in Computer Science" }],
      [{ text: "2016 - 2020" }],
      [{ text: "PROJECTS", bold: true }],
      [{ text: "Resume Parser", bold: true }],
      [{ text: "Jan 2024 - Mar 2024" }],
    ]);
    const result = await parseResumeFromPdf(bytes);

    expect(result.user.firstName).toBe("Jane");
    expect(result.user.lastName).toBe("Doe");
    expect(result.user.linkedinLink).toMatch(/linkedin\.com\/in\/janedoe/);
    expect(result.user.timezoneSuggestion).toBe("America/Los_Angeles");
    expect(result.education[0].school).toMatch(/Stanford University/);
    expect(result.education[0].degree).toBe("Bachelor");
    expect(result.workHistory[0].companyOrOrganization).toMatch(/Acme Corp/);
    expect(result.projects[0].name).toMatch(/Resume Parser/);
    // email is never extracted/mapped:
    expect(JSON.stringify(result)).not.toContain("@");
  });

  it("returns an empty-but-shaped result on a garbage PDF (no throw)", async () => {
    const result = await parseResumeFromPdf(new Uint8Array([0, 1, 2, 3]));
    expect(result.user.firstName).toBe("");
    expect(result.education).toEqual([]);
    expect(result.workHistory).toEqual([]);
  });
});
