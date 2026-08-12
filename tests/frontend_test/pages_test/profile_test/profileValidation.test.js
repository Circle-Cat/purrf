import { describe, it, expect } from "vitest";

import {
  validatePersonal,
  validateEducationRow,
  validateExperienceRow,
  isCompleteEducationRow,
  isCompleteExperienceRow,
} from "@/pages/Profile/profileValidation";

// Fixed so a rule about "the future" is decided by the argument and not by
// the day the suite happens to run.
const NOW = new Date(2026, 7, 15); // August 2026

const COMPLETE_EDUCATION = {
  institution: "Tsinghua University",
  degree: "BSc",
  field: "Computer Science",
  startMonth: "September",
  startYear: "2018",
  endMonth: "June",
  endYear: "2022",
};

const COMPLETE_EXPERIENCE = {
  title: "Backend Engineer",
  company: "Circle Cat",
  startMonth: "July",
  startYear: "2022",
  endMonth: "March",
  endYear: "2024",
};

describe("validatePersonal", () => {
  const COMPLETE = {
    firstName: "Yuji",
    lastName: "Wang",
    timezone: "Asia/Taipei",
  };

  it("accepts a personal block with a name and a timezone", () => {
    expect(validatePersonal(COMPLETE)).toEqual({});
  });

  it("flags a missing first name", () => {
    expect(validatePersonal({ ...COMPLETE, firstName: "" })).toEqual({
      firstName: "First name is required",
    });
  });

  it("flags a missing last name", () => {
    expect(validatePersonal({ ...COMPLETE, lastName: undefined })).toEqual({
      lastName: "Last name is required",
    });
  });

  it("flags a missing timezone", () => {
    expect(validatePersonal({ ...COMPLETE, timezone: "" })).toEqual({
      timezone: "Timezone is required",
    });
  });

  it("counts a whitespace-only name as missing", () => {
    expect(validatePersonal({ ...COMPLETE, firstName: "   " })).toEqual({
      firstName: "First name is required",
    });
  });

  it("leaves LinkedIn and preferred name optional", () => {
    expect(
      validatePersonal({ ...COMPLETE, linkedin: "", preferredName: "" }),
    ).toEqual({});
  });

  it("flags every missing field at once on an empty block", () => {
    expect(Object.keys(validatePersonal({})).sort()).toEqual([
      "firstName",
      "lastName",
      "timezone",
    ]);
  });

  it("survives a null block rather than throwing", () => {
    expect(Object.keys(validatePersonal(null)).sort()).toEqual([
      "firstName",
      "lastName",
      "timezone",
    ]);
  });
});

describe("validateEducationRow", () => {
  it("accepts a complete row", () => {
    expect(validateEducationRow(COMPLETE_EDUCATION, NOW)).toEqual({});
  });

  it("flags every required field on an empty row", () => {
    expect(validateEducationRow({}, NOW)).toEqual({
      institution: "School is required",
      degree: "Degree is required",
      field: "Field of study is required",
      startDate: "Start date is required",
      endDate: "End date is required",
    });
  });

  it("requires a non-blank field of study", () => {
    // The write-back helper used to accept an empty string here; the modal
    // never did. The strict reading wins.
    expect(
      validateEducationRow({ ...COMPLETE_EDUCATION, field: "  " }, NOW).field,
    ).toBe("Field of study is required");
  });

  it("flags a start date in the future", () => {
    expect(
      validateEducationRow(
        { ...COMPLETE_EDUCATION, startMonth: "September", startYear: "2026" },
        NOW,
      ).startDate,
    ).toBe("Start date cannot be in the future");
  });

  it("accepts a start date in the current month", () => {
    expect(
      validateEducationRow(
        {
          ...COMPLETE_EDUCATION,
          startMonth: "August",
          startYear: "2026",
          endMonth: "August",
          endYear: "2026",
        },
        NOW,
      ),
    ).toEqual({});
  });

  it("reports a missing start date rather than a future one", () => {
    expect(
      validateEducationRow({ ...COMPLETE_EDUCATION, startYear: "" }, NOW)
        .startDate,
    ).toBe("Start date is required");
  });

  it("flags an end date earlier than the start date", () => {
    expect(
      validateEducationRow(
        { ...COMPLETE_EDUCATION, endMonth: "June", endYear: "2017" },
        NOW,
      ).endDate,
    ).toBe("End date cannot be earlier than start date");
  });

  it("accepts an end date in the same month as the start date", () => {
    expect(
      validateEducationRow(
        {
          ...COMPLETE_EDUCATION,
          endMonth: "September",
          endYear: "2018",
        },
        NOW,
      ),
    ).toEqual({});
  });

  it("requires an end date even for an ongoing degree", () => {
    // Education has no "currently studying" flag; the modal always demanded
    // an end date and nothing here changes that.
    expect(
      validateEducationRow(
        { ...COMPLETE_EDUCATION, endMonth: "", endYear: "" },
        NOW,
      ).endDate,
    ).toBe("End date is required");
  });
});

describe("validateExperienceRow", () => {
  it("accepts a complete row", () => {
    expect(validateExperienceRow(COMPLETE_EXPERIENCE, NOW)).toEqual({});
  });

  it("flags every required field on an empty row", () => {
    expect(validateExperienceRow({}, NOW)).toEqual({
      title: "Title is required",
      company: "Company is required",
      startDate: "Start date is required",
      endDate: "End date is required",
    });
  });

  it("skips the end date for a role marked as current", () => {
    expect(
      validateExperienceRow(
        {
          ...COMPLETE_EXPERIENCE,
          isCurrentlyWorking: true,
          endMonth: "",
          endYear: "",
        },
        NOW,
      ),
    ).toEqual({});
  });

  it("flags a start date in the future", () => {
    expect(
      validateExperienceRow(
        {
          ...COMPLETE_EXPERIENCE,
          startMonth: "September",
          startYear: "2026",
          isCurrentlyWorking: true,
        },
        NOW,
      ).startDate,
    ).toBe("Start date cannot be in the future");
  });

  it("flags an end date earlier than the start date", () => {
    expect(
      validateExperienceRow(
        { ...COMPLETE_EXPERIENCE, endMonth: "January", endYear: "2021" },
        NOW,
      ).endDate,
    ).toBe("End date cannot be earlier than start date");
  });

  it("counts a whitespace-only company as missing", () => {
    expect(
      validateExperienceRow({ ...COMPLETE_EXPERIENCE, company: " " }, NOW)
        .company,
    ).toBe("Company is required");
  });
});

describe("isCompleteEducationRow", () => {
  it("accepts a row with every field filled in", () => {
    expect(isCompleteEducationRow(COMPLETE_EDUCATION, NOW)).toBe(true);
  });

  it("rejects a row whose field of study is an empty string", () => {
    // Deliberately stricter than the write-back helper it replaces, which
    // wrote such a row back to the profile.
    expect(
      isCompleteEducationRow({ ...COMPLETE_EDUCATION, field: "" }, NOW),
    ).toBe(false);
  });

  it("rejects a row whose end date precedes its start date", () => {
    expect(
      isCompleteEducationRow(
        { ...COMPLETE_EDUCATION, endMonth: "June", endYear: "2010" },
        NOW,
      ),
    ).toBe(false);
  });

  it("rejects a row missing its school", () => {
    expect(
      isCompleteEducationRow({ ...COMPLETE_EDUCATION, institution: "" }, NOW),
    ).toBe(false);
  });
});

describe("isCompleteExperienceRow", () => {
  it("accepts a row with a title, a company and a start date", () => {
    expect(isCompleteExperienceRow(COMPLETE_EXPERIENCE, NOW)).toBe(true);
  });

  it("accepts an ongoing role with no end date", () => {
    expect(
      isCompleteExperienceRow(
        {
          ...COMPLETE_EXPERIENCE,
          isCurrentlyWorking: true,
          endMonth: "",
          endYear: "",
        },
        NOW,
      ),
    ).toBe(true);
  });

  it("rejects a finished role with no end date", () => {
    // The write-back helper it replaces ignored the end date entirely.
    expect(
      isCompleteExperienceRow(
        { ...COMPLETE_EXPERIENCE, endMonth: "", endYear: "" },
        NOW,
      ),
    ).toBe(false);
  });

  it("rejects a row missing its company", () => {
    expect(
      isCompleteExperienceRow({ ...COMPLETE_EXPERIENCE, company: "" }, NOW),
    ).toBe(false);
  });
});
