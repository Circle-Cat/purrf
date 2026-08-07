import { describe, it, expect } from "vitest";

import {
  buildNewWriteBackRows,
  buildWriteBackPayload,
  hasPersonalWriteBackInput,
} from "@/pages/Recruiting/profileWriteBack";

const COMPLETE_EDUCATION = {
  id: "rpf-1",
  institution: "Tsinghua University",
  degree: "BSc",
  field: "Computer Science",
  startMonth: "September",
  startYear: "2018",
  endMonth: "June",
  endYear: "2022",
};

const COMPLETE_EXPERIENCE = {
  id: "rpf-2",
  title: "Backend Engineer",
  company: "Circle Cat",
  startMonth: "July",
  startYear: "2022",
  endMonth: "March",
  endYear: "2024",
};

describe("buildNewWriteBackRows", () => {
  it("keeps every complete row, however far down the list it sits", () => {
    // The row rules take an optional `now`, and `Array.prototype.filter`
    // hands its callback (row, index, array). Passing the rule to `filter`
    // bare would judge the second row against the number 1.
    const rows = buildNewWriteBackRows({
      education: [
        COMPLETE_EDUCATION,
        { ...COMPLETE_EDUCATION, id: "rpf-3", institution: "Peking" },
        { ...COMPLETE_EDUCATION, id: "rpf-4", institution: "Fudan" },
      ],
      experience: [
        COMPLETE_EXPERIENCE,
        { ...COMPLETE_EXPERIENCE, id: "rpf-5", company: "Other Co" },
      ],
    });

    expect(rows.education.map((r) => r.school)).toEqual([
      "Tsinghua University",
      "Peking",
      "Fudan",
    ]);
    expect(rows.workHistory.map((r) => r.companyOrOrganization)).toEqual([
      "Circle Cat",
      "Other Co",
    ]);
  });

  it("maps a complete education row into PATCH shape without its local id", () => {
    const { education } = buildNewWriteBackRows({
      education: [COMPLETE_EDUCATION],
    });

    expect(education).toEqual([
      {
        school: "Tsinghua University",
        degree: "BSc",
        fieldOfStudy: "Computer Science",
        startDate: "2018-09-01",
        endDate: "2022-06-01",
      },
    ]);
  });

  it("drops an education row whose field of study is blank", () => {
    // Deliberately stricter than before: this row used to be written back.
    const { education } = buildNewWriteBackRows({
      education: [{ ...COMPLETE_EDUCATION, field: "" }],
    });

    expect(education).toEqual([]);
  });

  it("drops a finished experience row that has no end date", () => {
    // Also stricter than before: the old rule ignored the end date entirely.
    const { workHistory } = buildNewWriteBackRows({
      experience: [{ ...COMPLETE_EXPERIENCE, endMonth: "", endYear: "" }],
    });

    expect(workHistory).toEqual([]);
  });

  it("keeps an ongoing experience row and sends a null end date", () => {
    const { workHistory } = buildNewWriteBackRows({
      experience: [
        {
          ...COMPLETE_EXPERIENCE,
          isCurrentlyWorking: true,
          endMonth: "",
          endYear: "",
        },
      ],
    });

    expect(workHistory).toEqual([
      {
        title: "Backend Engineer",
        companyOrOrganization: "Circle Cat",
        isCurrentJob: true,
        startDate: "2022-07-01",
        endDate: null,
      },
    ]);
  });

  it("returns empty lists when the form holds no rows at all", () => {
    expect(buildNewWriteBackRows({})).toEqual({
      education: [],
      workHistory: [],
    });
  });
});

describe("hasPersonalWriteBackInput", () => {
  // Pinned here rather than through the application form: that form now
  // requires a name and a timezone of every submission, so by the time one
  // goes out this can no longer be false. The guard stays because
  // `buildWriteBackPayload` is not the form's alone to reason about.
  it("is false for an empty personal block", () => {
    expect(hasPersonalWriteBackInput({})).toBe(false);
    expect(hasPersonalWriteBackInput(undefined)).toBe(false);
  });

  it("is false when every field is whitespace", () => {
    expect(hasPersonalWriteBackInput({ firstName: " ", lastName: "  " })).toBe(
      false,
    );
  });

  it("is true as soon as any one of the four fields is filled", () => {
    expect(hasPersonalWriteBackInput({ firstName: "Ann" })).toBe(true);
    expect(hasPersonalWriteBackInput({ lastName: "Liu" })).toBe(true);
    expect(hasPersonalWriteBackInput({ linkedin: "x" })).toBe(true);
    expect(hasPersonalWriteBackInput({ timezone: "Asia/Taipei" })).toBe(true);
  });
});

describe("buildWriteBackPayload only writes blocks the posting showed", () => {
  // Pinned here rather than through the form: after the read invariant, a
  // hidden block's rows always equal the profile's, so the form cannot
  // construct a case where this gate is the thing that saves you. It still
  // guards the payload builder for any caller that can.
  const STORED = {
    user: {
      firstName: "Cand",
      lastName: "Idate",
      preferredName: null,
      timezone: "Asia/Taipei",
      linkedinLink: null,
      communicationMethod: "email",
    },
    education: [],
    workHistory: [],
  };
  const PERSONAL = {
    firstName: "Cand",
    lastName: "Idate",
    timezone: "Asia/Taipei",
  };
  const rows = {
    education: [
      {
        school: "Peking University",
        degree: "MSc",
        fieldOfStudy: "Statistics",
        startDate: "2022-09-01",
        endDate: "2024-06-01",
      },
    ],
    workHistory: [
      {
        title: "Backend Engineer",
        companyOrOrganization: "Circle Cat",
        isCurrentJob: false,
        startDate: "2022-07-01",
        endDate: "2024-03-01",
      },
    ],
  };

  it("writes a block the posting showed", () => {
    const payload = buildWriteBackPayload(STORED, rows, PERSONAL, {
      education: true,
      workExperience: true,
    });
    expect(payload.education).toHaveLength(1);
    expect(payload.workHistory).toHaveLength(1);
  });

  it("leaves a hidden block alone even with rows to write", () => {
    const payload = buildWriteBackPayload(STORED, rows, PERSONAL, {
      education: false,
      workExperience: true,
    });
    expect(payload).not.toHaveProperty("education");
    expect(payload.workHistory).toHaveLength(1);
  });

  it("writes nothing at all when every block is hidden", () => {
    expect(
      buildWriteBackPayload(STORED, rows, PERSONAL, {
        education: false,
        workExperience: false,
      }),
    ).toBeNull();
  });

  it("clears a shown block the candidate emptied", () => {
    // Emptiness is not a reason to skip: on a block they were shown, it is a
    // deletion they asked for.
    const payload = buildWriteBackPayload(
      { ...STORED, education: [{ id: 41, school: "Tsinghua" }] },
      { education: [], workHistory: [] },
      PERSONAL,
      { education: true, workExperience: true },
    );
    expect(payload).toEqual({ education: [] });
  });
});

describe("buildNewWriteBackRows preserves a row's profile identity", () => {
  it("sends the profile row id back so the row is updated, not recreated", () => {
    const { education, workHistory } = buildNewWriteBackRows({
      education: [{ ...COMPLETE_EDUCATION, profileRowId: 41 }],
      experience: [{ ...COMPLETE_EXPERIENCE, profileRowId: 42 }],
    });
    expect(education[0].id).toBe(41);
    expect(workHistory[0].id).toBe(42);
  });

  it("sends no id for a row the candidate added here", () => {
    const { education } = buildNewWriteBackRows({
      education: [COMPLETE_EDUCATION],
    });
    expect(education[0]).not.toHaveProperty("id");
  });
});
