import { describe, it, expect } from "vitest";
import {
  answerKey,
  otherKey,
  profileKey,
  validateApplication,
} from "@/pages/Recruiting/applicationValidation";

const q = (overrides) => ({ id: "q1", label: "Q", ...overrides });

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

  it("is satisfied by one entry", () => {
    expect(
      validateApplication(
        [],
        {},
        {
          profileConfig: config,
          profile: {
            education: [{ school: "S" }],
            experience: [{ title: "T" }],
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
          profile: { education: [], experience: [] },
        },
      ),
    ).toEqual({});
  });

  it("checks no profile section when the caller passes none", () => {
    expect(validateApplication([], {})).toEqual({});
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
