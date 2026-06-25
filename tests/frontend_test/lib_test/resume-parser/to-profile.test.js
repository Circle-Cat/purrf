import { describe, it, expect } from "vitest";
import {
  classifyDegree,
  isLinkedin,
  splitName,
  toProfile,
} from "@/lib/resume-parser/to-profile";

describe("splitName", () => {
  it("last token is the last name; the rest is the first name", () => {
    expect(splitName("Mary Jane Watson")).toEqual({
      firstName: "Mary Jane",
      lastName: "Watson",
    });
  });
  it("folds a trailing suffix onto the last name", () => {
    expect(splitName("John Smith Jr.")).toEqual({
      firstName: "John",
      lastName: "Smith Jr.",
    });
  });
});

describe("classifyDegree", () => {
  it("maps known degrees to the Purrf enum", () => {
    expect(classifyDegree("Bachelor of Science")).toBe("Bachelor");
    expect(classifyDegree("Ph.D. in Physics")).toBe("Doctorate");
    expect(classifyDegree("Juris Doctor")).toBe("Professional");
  });
  it("returns undefined for unsupported degrees (High School)", () => {
    expect(classifyDegree("High School Diploma")).toBeUndefined();
  });
});

describe("isLinkedin", () => {
  it("only matches linkedin.com URLs", () => {
    expect(isLinkedin("linkedin.com/in/jane")).toBe(true);
    expect(isLinkedin("github.com/jane")).toBe(false);
  });
});

describe("toProfile", () => {
  it("assembles a ParsedResume; email is never present; timezone is inferred", () => {
    const out = toProfile({
      profile: {
        name: "Jane Doe",
        phone: "(123) 456-7890",
        url: "github.com/jane",
        location: "San Francisco, CA",
      },
      education: [
        {
          school: "Stanford University",
          degree: "Bachelor of Science in CS",
          fieldOfStudy: "CS",
          startDate: "2016-01-01",
          endDate: "2020-01-01",
        },
      ],
      workHistory: [
        {
          title: "Engineer",
          companyOrOrganization: "Acme",
          startDate: "2020-01-01",
          endDate: null,
          isCurrentJob: true,
        },
      ],
      summary: "A summary line.",
    });
    expect(out.user).toEqual({
      firstName: "Jane",
      lastName: "Doe",
      phone: "(123) 456-7890",
      linkedinLink: undefined,
      timezoneSuggestion: "America/Los_Angeles",
    });
    expect(out.education[0].degree).toBe("Bachelor");
    expect(out.workHistory[0].isCurrentJob).toBe(true);
    expect(out.unmapped.summary).toBe("A summary line.");
    expect(JSON.stringify(out)).not.toContain("@");
  });
});
