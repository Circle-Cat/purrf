import { describe, it, expect } from "vitest";
import { profileToApplicationForm } from "@/pages/Recruiting/profilePrefill";

describe("profileToApplicationForm", () => {
  it("maps user fields to the personal shape (linkedinLink renamed)", () => {
    const fetched = {
      user: {
        firstName: "Ann",
        lastName: "Liu",
        linkedinLink: "https://linkedin.com/in/annliu",
        timezone: "America/Los_Angeles",
      },
      education: [],
      workHistory: [],
    };

    expect(profileToApplicationForm(fetched).personal).toEqual({
      firstName: "Ann",
      lastName: "Liu",
      linkedin: "https://linkedin.com/in/annliu",
      timezone: "America/Los_Angeles",
    });
  });

  it("maps an education row with school/field renamed, dates split, and a truthy id", () => {
    const fetched = {
      user: {},
      education: [
        {
          id: 33,
          school: "UC Berkeley",
          degree: "Bachelor",
          fieldOfStudy: "Computer Science",
          startDate: "2018-09-01",
          endDate: "2022-05-01",
        },
      ],
      workHistory: [],
    };

    const result = profileToApplicationForm(fetched).education;
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      institution: "UC Berkeley",
      degree: "Bachelor",
      field: "Computer Science",
      startMonth: "September",
      startYear: "2018",
      endMonth: "May",
      endYear: "2022",
    });
    expect(result[0].id).toBeTruthy();
  });

  it("maps a work-history row with company/title renamed and dates split", () => {
    const fetched = {
      user: {},
      education: [],
      workHistory: [
        {
          id: 42,
          title: "Software Engineer",
          companyOrOrganization: "Acme",
          isCurrentJob: false,
          startDate: "2020-06-01",
          endDate: "2023-01-01",
        },
      ],
    };

    const result = profileToApplicationForm(fetched).experience;
    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      title: "Software Engineer",
      company: "Acme",
      isCurrentlyWorking: false,
      startMonth: "June",
      startYear: "2020",
      endMonth: "January",
      endYear: "2023",
    });
    expect(result[0].id).toBeTruthy();
  });

  it("blanks the end date for a current job regardless of any stored endDate", () => {
    const fetched = {
      user: {},
      education: [],
      workHistory: [
        {
          title: "Engineer",
          companyOrOrganization: "Acme",
          isCurrentJob: true,
          startDate: "2020-06-01",
          endDate: "2023-01-01",
        },
      ],
    };

    const result = profileToApplicationForm(fetched).experience[0];
    expect(result.isCurrentlyWorking).toBe(true);
    expect(result.endMonth).toBe("");
    expect(result.endYear).toBe("");
  });

  it("assigns each row a distinct id", () => {
    const fetched = {
      user: {},
      education: [
        {
          school: "A",
          degree: "d",
          fieldOfStudy: "f",
          startDate: null,
          endDate: null,
        },
        {
          school: "B",
          degree: "d",
          fieldOfStudy: "f",
          startDate: null,
          endDate: null,
        },
      ],
      workHistory: [],
    };

    const [first, second] = profileToApplicationForm(fetched).education;
    expect(first.id).not.toBe(second.id);
  });

  it("returns empty defaults for an absent or fully-empty profile", () => {
    const emptyResult = {
      personal: { firstName: "", lastName: "", linkedin: "", timezone: "" },
      education: [],
      experience: [],
    };
    expect(profileToApplicationForm(undefined)).toEqual(emptyResult);
    expect(profileToApplicationForm({})).toEqual(emptyResult);
  });
});

describe("profileToApplicationForm keeps each row's profile id", () => {
  // Without it, saving a changed list recreates every row in it, including
  // the ones the candidate never touched.
  it("carries the profile row id alongside the form's own local id", () => {
    const value = profileToApplicationForm({
      user: {},
      education: [
        {
          id: 41,
          school: "Tsinghua University",
          degree: "BSc",
          fieldOfStudy: "Computer Science",
          startDate: "2018-09-01",
          endDate: "2022-06-01",
        },
      ],
      workHistory: [
        {
          id: 42,
          title: "Backend Engineer",
          companyOrOrganization: "Circle Cat",
          startDate: "2022-07-01",
          endDate: "2024-03-01",
        },
      ],
    });

    expect(value.education[0].profileRowId).toBe(41);
    expect(value.experience[0].profileRowId).toBe(42);
    // The local id is still the form's own, not the profile's.
    expect(value.education[0].id).not.toBe(41);
  });

  it("leaves the profile id undefined when the profile row has none", () => {
    const value = profileToApplicationForm({
      user: {},
      education: [{ school: "Tsinghua University" }],
      workHistory: [],
    });
    expect(value.education[0].profileRowId).toBeUndefined();
  });
});
