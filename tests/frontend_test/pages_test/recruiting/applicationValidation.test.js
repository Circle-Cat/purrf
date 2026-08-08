import { describe, it, expect } from "vitest";
import {
  answerKey,
  otherKey,
  profileKey,
  rowKey,
  validateApplication,
} from "@/pages/Recruiting/applicationValidation";

const q = (overrides) => ({ id: "q1", label: "Q", ...overrides });

const PERSONAL = {
  firstName: "Yuji",
  lastName: "Wang",
  timezone: "Asia/Taipei",
};

const EDUCATION_ROW = {
  id: "rpf-1",
  institution: "Tsinghua University",
  degree: "BSc",
  field: "Computer Science",
  startMonth: "September",
  startYear: "2018",
  endMonth: "June",
  endYear: "2022",
};

const EXPERIENCE_ROW = {
  id: "rpf-2",
  title: "Backend Engineer",
  company: "Circle Cat",
  startMonth: "July",
  startYear: "2022",
  endMonth: "March",
  endYear: "2024",
};

describe("required", () => {
  it("accepts a form with nothing required", () => {
    expect(validateApplication([q({ type: "short_text" })], {})).toEqual({});
  });

  it.each([undefined, "", "   ", []])(
    "rejects %p for a required question",
    (value) => {
      const errors = validateApplication(
        [q({ type: "short_text", label: "Where?", required: true })],
        { q1: value },
      );
      expect(errors[answerKey("q1")]).toBe("This question is required");
    },
  );

  it.each([0, false])("treats the recorded value %p as answered", (value) => {
    expect(
      validateApplication([q({ type: "short_text", required: true })], {
        q1: value,
      }),
    ).toEqual({});
  });

  it("does not require a question the form is not showing", () => {
    // Its rule stopped matching, so it is not on screen to answer.
    const errors = validateApplication(
      [
        q({
          id: "q1",
          type: "single_choice",
          options: ["Yes", "No"],
        }),
        q({
          id: "q2",
          type: "short_text",
          required: true,
          showWhen: { questionId: "q1", equals: "Yes" },
        }),
      ],
      { q1: "No" },
    );
    expect(errors).toEqual({});
  });
});

describe("choice questions", () => {
  const single = q({
    type: "single_choice",
    label: "Need sponsorship?",
    options: ["Yes", "No"],
  });

  it("rejects a value that is not one of the options", () => {
    expect(
      validateApplication([single], { q1: "maybe" })[answerKey("q1")],
    ).toBe("Pick one of the listed options");
  });

  it("accepts a listed option", () => {
    expect(validateApplication([single], { q1: "No" })).toEqual({});
  });

  const multi = q({
    type: "multi_choice",
    label: "Teams?",
    options: ["A", "B", "C"],
    maxSelections: 2,
  });

  it("rejects more selections than the cap", () => {
    expect(
      validateApplication([multi], { q1: ["A", "B", "C"] })[answerKey("q1")],
    ).toBe("Pick at most 2 options");
  });

  it("accepts exactly the cap", () => {
    expect(validateApplication([multi], { q1: ["A", "B"] })).toEqual({});
  });

  it("says option, singular, when only one may be picked", () => {
    expect(
      validateApplication([{ ...multi, maxSelections: 1 }], { q1: ["A", "B"] })[
        answerKey("q1")
      ],
    ).toBe("Pick at most 1 option");
  });

  it("rejects a selection that is not one of the options", () => {
    expect(
      validateApplication([multi], { q1: ["A", "Z"] })[answerKey("q1")],
    ).toBe("Pick from the listed options");
  });

  it("has no cap when maxSelections is unset", () => {
    expect(
      validateApplication([{ ...multi, maxSelections: undefined }], {
        q1: ["A", "B", "C"],
      }),
    ).toEqual({});
  });
});

describe("long text", () => {
  const long = q({ type: "long_text", label: "Why?", maxLength: 10 });

  it("rejects more characters than the budget", () => {
    expect(
      validateApplication([long], { q1: "x".repeat(11) })[answerKey("q1")],
    ).toBe("Keep this under 10 characters");
  });

  it("accepts exactly the budget", () => {
    expect(validateApplication([long], { q1: "x".repeat(10) })).toEqual({});
  });

  it("counts characters, so a Chinese answer is measured the same way", () => {
    // The reason maxWords was dropped: whitespace splitting makes one limit
    // bind for some candidates and never for others.
    expect(
      validateApplication([long], { q1: "我很喜欢这份工作真的非常喜欢" })[
        answerKey("q1")
      ],
    ).toBe("Keep this under 10 characters");
  });
});

describe("hard ceiling", () => {
  it("rejects a short text answer past the hard ceiling", () => {
    const questions = [{ id: "q1", type: "short_text", label: "City" }];
    const errors = validateApplication(questions, { q1: "x".repeat(256) });
    expect(errors["answer:q1"]).toBe("Keep this under 255 characters");
  });

  it("accepts a short text answer of exactly the hard ceiling", () => {
    const questions = [{ id: "q1", type: "short_text", label: "City" }];
    expect(validateApplication(questions, { q1: "x".repeat(255) })).toEqual({});
  });

  it("holds an unbudgeted long text answer to the fallback ceiling", () => {
    const questions = [{ id: "q1", type: "long_text", label: "Why" }];
    const errors = validateApplication(questions, { q1: "x".repeat(5001) });
    expect(errors["answer:q1"]).toBe("Keep this under 5000 characters");
  });
});

describe("exact text", () => {
  const exact = q({
    type: "exact_text",
    label: "Confirm",
    expectedValue: "I AGREE",
  });

  it("accepts the phrase with surrounding whitespace trimmed", () => {
    expect(validateApplication([exact], { q1: "  I AGREE  " })).toEqual({});
  });

  it("rejects a different case, since exact is the point", () => {
    expect(
      validateApplication([exact], { q1: "i agree" })[answerKey("q1")],
    ).toBe("Type I AGREE exactly");
  });
});

describe("the Other free text", () => {
  const withOther = q({
    type: "single_choice",
    label: "How did you hear?",
    options: ["Friend", "Other"],
    otherOption: "Other",
  });

  it("is required once Other is picked", () => {
    expect(
      validateApplication([withOther], { q1: "Other", q1__other: "  " })[
        otherKey("q1")
      ],
    ).toBe("Please describe your answer");
  });

  it("is not required when Other is not picked", () => {
    expect(validateApplication([withOther], { q1: "Friend" })).toEqual({});
  });

  it("is satisfied by any text", () => {
    expect(
      validateApplication([withOther], { q1: "Other", q1__other: "A podcast" }),
    ).toEqual({});
  });
});

describe("profile sections", () => {
  const config = { education: "required", workExperience: "required" };

  it("requires an entry in each section the posting marks required", () => {
    const errors = validateApplication(
      [],
      {},
      {
        profileConfig: config,
        profile: { education: [], experience: [] },
      },
    );
    expect(errors[profileKey("education")]).toBe(
      "Add at least one education entry",
    );
    expect(errors[profileKey("experience")]).toBe(
      "Add at least one experience entry",
    );
  });

  it("is satisfied by one complete entry", () => {
    expect(
      validateApplication(
        [],
        {},
        {
          profileConfig: config,
          profile: {
            personal: PERSONAL,
            education: [EDUCATION_ROW],
            experience: [EXPERIENCE_ROW],
          },
        },
      ),
    ).toEqual({});
  });

  it("asks for nothing when the sections are optional or off", () => {
    expect(
      validateApplication(
        [],
        {},
        {
          profileConfig: { education: "optional", workExperience: "off" },
          profile: { personal: PERSONAL, education: [], experience: [] },
        },
      ),
    ).toEqual({});
  });

  it("checks no profile section when the caller passes none", () => {
    expect(validateApplication([], {})).toEqual({});
  });
});

describe("personal fields", () => {
  const withPersonal = (personal) =>
    validateApplication([], {}, { profile: { personal } });

  it("accepts a first name, a last name and a timezone", () => {
    expect(withPersonal(PERSONAL)).toEqual({});
  });

  it("requires all three, whatever the posting's profileConfig says", () => {
    // The form marks them with a plain asterisk, not a configurable one.
    const errors = validateApplication(
      [],
      {},
      {
        profileConfig: { education: "off", workExperience: "off" },
        profile: {},
      },
    );
    expect(errors[profileKey("firstName")]).toBe("First name is required");
    expect(errors[profileKey("lastName")]).toBe("Last name is required");
    expect(errors[profileKey("timezone")]).toBe("Timezone is required");
  });

  it("keys each problem under the field that has it", () => {
    expect(withPersonal({ ...PERSONAL, lastName: "  " })).toEqual({
      [profileKey("lastName")]: "Last name is required",
    });
  });

  it("checks nothing when the caller hands over no profile at all", () => {
    expect(validateApplication([q({ required: false })], {})).toEqual({});
  });
});

describe("profile rows", () => {
  const check = (profile, profileConfig) =>
    validateApplication([], {}, { profileConfig, profile });

  it("requires every field of an education row the candidate added", () => {
    const errors = check(
      { personal: PERSONAL, education: [{ id: "rpf-9" }] },
      { education: "optional" },
    );
    expect(errors[rowKey("education", "rpf-9", "institution")]).toBe(
      "School is required",
    );
    expect(errors[rowKey("education", "rpf-9", "field")]).toBe(
      "Field of study is required",
    );
    expect(errors[rowKey("education", "rpf-9", "endDate")]).toBe(
      "End date is required",
    );
  });

  it("checks a row even when the section is only optional", () => {
    // Optional means "you need not add one", not "a half-filled one is fine".
    const errors = check(
      { personal: PERSONAL, education: [{ ...EDUCATION_ROW, degree: "" }] },
      { education: "optional" },
    );
    expect(errors[rowKey("education", "rpf-1", "degree")]).toBe(
      "Degree is required",
    );
  });

  it("checks no row in a section the posting switched off", () => {
    // The section is not rendered at all, so an error there could never be
    // seen, let alone fixed.
    expect(
      check(
        { personal: PERSONAL, education: [{ id: "rpf-9" }] },
        { education: "off" },
      ),
    ).toEqual({});
  });

  it("asks for the section itself only while it is still empty", () => {
    const errors = check(
      { personal: PERSONAL, education: [{ id: "rpf-9" }] },
      { education: "required" },
    );
    expect(errors[profileKey("education")]).toBeUndefined();
    expect(errors[rowKey("education", "rpf-9", "institution")]).toBe(
      "School is required",
    );
  });

  it("keys an experience row under its own section", () => {
    const errors = check(
      { personal: PERSONAL, experience: [{ ...EXPERIENCE_ROW, company: "" }] },
      { workExperience: "optional" },
    );
    expect(errors[rowKey("experience", "rpf-2", "company")]).toBe(
      "Company is required",
    );
  });

  it("lets an ongoing role skip its end date", () => {
    expect(
      check(
        {
          personal: PERSONAL,
          experience: [
            {
              ...EXPERIENCE_ROW,
              isCurrentlyWorking: true,
              endMonth: "",
              endYear: "",
            },
          ],
        },
        { workExperience: "required" },
      ),
    ).toEqual({});
  });
});

describe("the order problems are reported in", () => {
  it("puts the profile before the answers, the way the page does", () => {
    // The first key is what the form scrolls to, and the profile block is
    // rendered above the questions.
    const errors = validateApplication(
      [q({ id: "q1", required: true })],
      {},
      { profile: { personal: {} } },
    );
    expect(Object.keys(errors)[0]).toBe(profileKey("firstName"));
    expect(Object.keys(errors)).toContain(answerKey("q1"));
  });
});

describe("key helpers", () => {
  it("keeps a question's own answer distinct from its Other free text", () => {
    const keys = [
      answerKey("q1"),
      otherKey("q1"),
      answerKey("q2"),
      profileKey("education"),
      profileKey("experience"),
    ];
    expect(new Set(keys).size).toBe(keys.length);
  });
});

describe("the résumé a posting requires", () => {
  const check = (resume, level) =>
    validateApplication(
      [],
      {},
      {
        profileConfig: { resume: level },
        profile: { personal: PERSONAL },
        resume,
      },
    );

  it("asks for one when the posting requires it and none is attached", () => {
    expect(check({ objectKey: null }, "required")[profileKey("resume")]).toBe(
      "A résumé is required",
    );
  });

  it("is satisfied by a résumé carried over from a previous application", () => {
    // The key is what the server looks at; where it came from is irrelevant.
    expect(check({ objectKey: "resumes/7.pdf" }, "required")).toEqual({});
  });

  it("treats a cleared key as no résumé, however it was cleared", () => {
    // The upload path clears it with `undefined`, Remove with `null`.
    expect(
      check({ objectKey: undefined }, "required")[profileKey("resume")],
    ).toBe("A résumé is required");
  });

  it("asks for nothing when the posting only invites one", () => {
    expect(check({ objectKey: null }, "optional")).toEqual({});
  });

  it("asks for nothing when the posting collects none at all", () => {
    // `off` means an upload is prefill-only and the server discards the file;
    // demanding one would ask for a file that is thrown away.
    expect(check({ objectKey: null }, "off")).toEqual({});
  });

  it("asks for nothing when the posting says nothing about résumés", () => {
    expect(check({ objectKey: null }, undefined)).toEqual({});
  });

  it("comes before the answers, since the résumé sits above them", () => {
    const errors = validateApplication(
      [q({ id: "q1", required: true })],
      {},
      {
        profileConfig: { resume: "required" },
        profile: { personal: PERSONAL },
        resume: { objectKey: null },
      },
    );
    expect(Object.keys(errors)[0]).toBe(profileKey("resume"));
  });
});
