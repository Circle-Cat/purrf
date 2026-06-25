import { describe, it, expect } from "vitest";
import { getTextWithHighestScore } from "@/lib/resume-parser/feature-scoring";

const item = (text) => ({
  text,
  x: 0,
  y: 0,
  width: 10,
  height: 11,
  fontName: "Helvetica",
  hasEOL: false,
});
const hasDigit = (i) => /\d/.test(i.text);
const matchDigits = (i) => i.text.match(/\d+/);

describe("getTextWithHighestScore", () => {
  it("returns the highest scoring item's text", () => {
    const items = [item("hello"), item("world 42")];
    const out = getTextWithHighestScore(items, [[hasDigit, 4]]);
    expect(out).toBe("world 42");
  });
  it("returnMatchOnly returns the matched substring", () => {
    const items = [item("call 5551234 now")];
    const out = getTextWithHighestScore(items, [[matchDigits, 4, true]]);
    expect(out).toBe("5551234");
  });
  it("returns '' when the best score is <= 0", () => {
    const items = [item("nope")];
    const out = getTextWithHighestScore(items, [[hasDigit, 4]]);
    expect(out).toBe("");
  });
  it("concatTies joins texts tied at the best score", () => {
    const items = [item("aa 11"), item("bb 22")];
    const out = getTextWithHighestScore(items, [[hasDigit, 4]], {
      concatTies: true,
    });
    expect(out).toBe("aa 11 bb 22");
  });
  it("isolates a substring match from the line's negative features", () => {
    const hasLetter = (i) => /[a-z]/i.test(i.text);
    const matchPhone = (i) => i.text.match(/\d{3}-\d{4}/);
    const items = [item("Tel: 555-1234 email a@b.com")];
    // Without isolation, hasLetter (-4) would cancel matchPhone (+4) -> "".
    const out = getTextWithHighestScore(items, [
      [matchPhone, 4, true],
      [hasLetter, -4],
    ]);
    expect(out).toBe("555-1234");
  });
  it("allowNonPositive returns the top candidate even at score <= 0", () => {
    const isBoldFont = (i) => i.fontName === "Bold";
    const items = [item("Acme Corp"), item("2020")];
    const out = getTextWithHighestScore(items, [[isBoldFont, 2]], {
      allowNonPositive: true,
    });
    expect(out).toBe("Acme Corp");
  });
});
