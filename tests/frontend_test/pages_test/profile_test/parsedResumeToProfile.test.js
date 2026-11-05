import { describe, it, expect } from "vitest";

import {
  yearMonthToParts,
  parsedResumeToProfile,
  mergeParsedIntoProfile,
} from "@/pages/Profile/parsedResumeToProfile";

describe("yearMonthToParts", () => {
  it("splits a YYYY-MM string into a month name and a year string", () => {
    expect(yearMonthToParts("2022-09")).toEqual({
      month: "September",
      year: "2022",
    });
  });

  it("returns empty parts for null, empty, or malformed input", () => {
    expect(yearMonthToParts(null)).toEqual({ month: "", year: "" });
    expect(yearMonthToParts("")).toEqual({ month: "", year: "" });
    expect(yearMonthToParts("nonsense")).toEqual({ month: "", year: "" });
  });
});

describe("parsedResumeToProfile", () => {
  it("maps user fields to the personal shape (linkedin renamed, phone dropped)", () => {
    const parsed = {
      user: {
        firstName: "Ann",
        lastName: "Liu",
        phone: "+1 415 555 0142",
        linkedinLink: "https://linkedin.com/in/annliu",
        timezoneSuggestion: "America/Los_Angeles",
      },
      education: [],
      workHistory: [],
    };

    expect(parsedResumeToProfile(parsed).personal).toEqual({
      firstName: "Ann",
      lastName: "Liu",
      linkedin: "https://linkedin.com/in/annliu",
      timezone: "America/Los_Angeles",
    });
  });

  it("maps education entries with school/field renamed and dates split", () => {
    const parsed = {
      user: {},
      education: [
        {
          school: "UC Berkeley",
          degree: "Bachelor",
          fieldOfStudy: "Computer Science",
          startDate: "2022-08",
          endDate: "2026-05",
        },
      ],
      workHistory: [],
    };

    expect(parsedResumeToProfile(parsed).education).toEqual([
      {
        institution: "UC Berkeley",
        degree: "Bachelor",
        field: "Computer Science",
        startMonth: "August",
        startYear: "2022",
        endMonth: "May",
        endYear: "2026",
      },
    ]);
  });

  it("blanks an unclassifiable degree (undefined) to an empty string", () => {
    const parsed = {
      user: {},
      education: [
        { school: "Some College", degree: undefined, fieldOfStudy: "X" },
      ],
      workHistory: [],
    };

    expect(parsedResumeToProfile(parsed).education[0].degree).toBe("");
  });

  it("maps work history with company/isCurrentlyWorking renamed and dates split", () => {
    const parsed = {
      user: {},
      education: [],
      workHistory: [
        {
          title: "Research Assistant",
          companyOrOrganization: "Robotics Lab",
          startDate: "2024-01",
          endDate: null,
          isCurrentJob: true,
        },
      ],
    };

    expect(parsedResumeToProfile(parsed).experience).toEqual([
      {
        title: "Research Assistant",
        company: "Robotics Lab",
        isCurrentlyWorking: true,
        startMonth: "January",
        startYear: "2024",
        endMonth: "",
        endYear: "",
      },
    ]);
  });

  it("drops projects and summary, returning only personal/education/experience", () => {
    const parsed = {
      user: { firstName: "A" },
      education: [],
      workHistory: [],
      projects: [{ name: "Side project" }],
      unmapped: { summary: "A summary" },
    };

    expect(Object.keys(parsedResumeToProfile(parsed)).sort()).toEqual([
      "education",
      "experience",
      "personal",
    ]);
  });

  it("is graceful on an empty / missing-fields parse result", () => {
    expect(parsedResumeToProfile({})).toEqual({
      personal: { firstName: "", lastName: "", linkedin: "", timezone: "" },
      education: [],
      experience: [],
    });
  });
});

describe("mergeParsedIntoProfile", () => {
  const emptyProfile = () => ({
    personal: { firstName: "", lastName: "", linkedin: "", timezone: "" },
    education: [],
    experience: [],
  });

  it("fills empty existing scalar fields from the incoming values", () => {
    const existing = emptyProfile();
    const incoming = {
      ...emptyProfile(),
      personal: {
        firstName: "Ann",
        lastName: "Liu",
        linkedin: "",
        timezone: "",
      },
    };

    expect(mergeParsedIntoProfile(existing, incoming).personal).toEqual({
      firstName: "Ann",
      lastName: "Liu",
      linkedin: "",
      timezone: "",
    });
  });

  it("overwrites an existing scalar when incoming differs, but keeps it when incoming is empty", () => {
    const existing = {
      ...emptyProfile(),
      personal: {
        firstName: "Annie",
        lastName: "Liu",
        linkedin: "old-url",
        timezone: "America/Los_Angeles",
      },
    };
    const incoming = {
      ...emptyProfile(),
      personal: {
        firstName: "Ann",
        lastName: "",
        linkedin: "new-url",
        timezone: "",
      },
    };

    // firstName differs+non-empty -> overwrite; lastName/timezone empty -> keep.
    expect(mergeParsedIntoProfile(existing, incoming).personal).toEqual({
      firstName: "Ann",
      lastName: "Liu",
      linkedin: "new-url",
      timezone: "America/Los_Angeles",
    });
  });

  it("replaces the whole education array when incoming has entries", () => {
    const existing = {
      ...emptyProfile(),
      education: [
        {
          institution: "Old School",
          degree: "",
          field: "",
          startMonth: "",
          startYear: "",
          endMonth: "",
          endYear: "",
        },
      ],
    };
    const incoming = {
      ...emptyProfile(),
      education: [
        {
          institution: "UC Berkeley",
          degree: "Bachelor",
          field: "CS",
          startMonth: "August",
          startYear: "2022",
          endMonth: "",
          endYear: "",
        },
      ],
    };

    expect(mergeParsedIntoProfile(existing, incoming).education).toEqual(
      incoming.education,
    );
  });

  it("keeps the existing education array when incoming has none", () => {
    const existing = {
      ...emptyProfile(),
      education: [
        {
          institution: "Old School",
          degree: "",
          field: "",
          startMonth: "",
          startYear: "",
          endMonth: "",
          endYear: "",
        },
      ],
    };

    expect(mergeParsedIntoProfile(existing, emptyProfile()).education).toEqual(
      existing.education,
    );
  });

  it("replaces experience wholesale the same way", () => {
    const existing = {
      ...emptyProfile(),
      experience: [
        {
          title: "Old",
          company: "X",
          isCurrentlyWorking: false,
          startMonth: "",
          startYear: "",
          endMonth: "",
          endYear: "",
        },
      ],
    };
    const incoming = {
      ...emptyProfile(),
      experience: [
        {
          title: "New",
          company: "Y",
          isCurrentlyWorking: true,
          startMonth: "",
          startYear: "",
          endMonth: "",
          endYear: "",
        },
      ],
    };

    expect(mergeParsedIntoProfile(existing, incoming).experience).toEqual(
      incoming.experience,
    );
  });

  it("is graceful when existing is undefined (treats it as an empty profile)", () => {
    const incoming = {
      ...emptyProfile(),
      personal: { firstName: "Ann", lastName: "", linkedin: "", timezone: "" },
    };

    expect(mergeParsedIntoProfile(undefined, incoming)).toEqual(incoming);
  });
});
