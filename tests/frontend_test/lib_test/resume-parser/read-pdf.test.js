import { describe, it, expect } from "vitest";
import { readPdf } from "@/lib/resume-parser/read-pdf";
import { makeResumePdf } from "./resume.helper";

describe("readPdf", () => {
  it("extracts text, coordinates, and a Bold font name", async () => {
    const bytes = await makeResumePdf([
      [{ text: "Jane Doe", bold: true, size: 16 }],
      [{ text: "jane@example.com" }],
    ]);
    const items = await readPdf(bytes);
    const texts = items.map((i) => i.text);
    expect(texts.join(" ")).toContain("Jane Doe");
    expect(texts.join(" ")).toContain("jane@example.com");
    const name = items.find((i) => i.text.includes("Jane"));
    expect(name.fontName.toLowerCase()).toContain("bold");
    expect(name.x).toBeGreaterThan(0);
    expect(name.height).toBeGreaterThan(0);
  });

  it("returns [] (never throws) on garbage bytes", async () => {
    const items = await readPdf(new Uint8Array([1, 2, 3, 4]));
    expect(items).toEqual([]);
  });
});
