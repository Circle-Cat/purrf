import { describe, it, expect } from "vitest";
import * as F from "@/lib/resume-parser/lib/features";

const item = (text, over = {}) => ({
  text,
  x: 0,
  y: 0,
  width: 10,
  height: 11,
  fontName: "Helvetica",
  hasEOL: false,
  ...over,
});

describe("features predicates", () => {
  it("isBold reads the font name substring", () => {
    expect(F.isBold(item("X", { fontName: "ABCDEE+Helvetica-Bold" }))).toBe(
      true,
    );
    expect(F.isBold(item("X", { fontName: "Helvetica" }))).toBe(false);
  });
  it("isAllUpperWithLetter requires a letter and all-caps", () => {
    expect(F.isAllUpperWithLetter(item("EXPERIENCE"))).toBe(true);
    expect(F.isAllUpperWithLetter(item("Experience"))).toBe(false);
    expect(F.isAllUpperWithLetter(item("(123)"))).toBe(false);
  });
  it("matchName accepts unicode/apostrophe/hyphen names, rejects emails", () => {
    expect(F.matchName(item("José O'Connor-Łukasz"))).toBeTruthy();
    expect(F.matchName(item("jane@example.com"))).toBeFalsy();
  });
  it("matchPhone extracts the phone substring", () => {
    expect(F.matchPhone(item("(123) 456-7890"))[0]).toBe("(123) 456-7890");
  });
  it("matchPhone extracts an international +country number", () => {
    expect(F.matchPhone(item("+44 07700900123 | a@b.com"))[0]).toBe(
      "+44 07700900123",
    );
  });
  it("matchCityState accepts code and full state name", () => {
    expect(F.matchCityState(item("New York, NY"))).toBeTruthy();
    expect(F.matchCityState(item("Berkeley, California"))).toBeTruthy();
  });
  it("hasSchool / hasDegree keyword detection", () => {
    expect(F.hasSchool(item("Stanford University"))).toBe(true);
    expect(F.hasDegree(item("Bachelor of Science"))).toBe(true);
    expect(F.hasDegree(item("B.S. Computer Science"))).toBe(true);
    expect(F.hasDegree(item("Mathematics BSc"))).toBe(true);
    expect(F.hasDegree(item("MSc Data Science"))).toBe(true);
  });
  it("isContactLine matches email/phone/url/city-state strings", () => {
    expect(F.isContactLine("jane@example.com")).toBe(true);
    expect(F.isContactLine("linkedin.com/in/jane")).toBe(true);
    expect(F.isContactLine("EXPERIENCE")).toBe(false);
  });
});
