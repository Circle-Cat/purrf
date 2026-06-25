import { describe, it, expect } from "vitest";
import { extractProfile } from "@/lib/resume-parser/extract-profile";

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

describe("extractProfile", () => {
  it("pulls name, phone, location, and url out of a header", () => {
    const profile = [
      [tok("Jane Doe", { fontName: "Helvetica-Bold" })],
      [tok("(123) 456-7890")],
      [tok("New York, NY")],
      [tok("linkedin.com/in/janedoe")],
    ];
    const out = extractProfile(profile);
    expect(out.name).toBe("Jane Doe");
    expect(out.phone).toBe("(123) 456-7890");
    expect(out.location).toMatch(/New York, NY/);
    expect(out.url).toMatch(/linkedin\.com\/in\/janedoe/);
  });
  it("does not pick an email as the name", () => {
    const profile = [[tok("jane@example.com")], [tok("Jane Doe")]];
    expect(extractProfile(profile).name).toBe("Jane Doe");
  });
});
