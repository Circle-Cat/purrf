import { describe, it, expect } from "vitest";
import {
  basicsKey,
  optionKey,
  questionKey,
  ruleKey,
  validatePosting,
} from "@/pages/Recruiting/postings/postingValidation";

/** A draft that passes every rule, so each case can break exactly one thing. */
const valid = (overrides = {}) => ({
  title: "Backend intern",
  cooldownDays: 0,
  formSchema: { questions: [] },
  screenRules: { rules: [] },
  ...overrides,
});

const withQuestions = (...questions) => valid({ formSchema: { questions } });

const choice = (overrides = {}) => ({
  id: "q1",
  type: "single_choice",
  label: "Need sponsorship?",
  options: ["Yes", "No"],
  ...overrides,
});

describe("basics", () => {
  it("accepts a complete draft", () => {
    expect(validatePosting(valid())).toEqual({});
  });

  it.each([undefined, "", "   "])("rejects the title %p", (title) => {
    expect(validatePosting(valid({ title }))[basicsKey("title")]).toBe(
      "Title is required",
    );
  });

  it("rejects a negative cooldown", () => {
    expect(
      validatePosting(valid({ cooldownDays: -1 }))[basicsKey("cooldownDays")],
    ).toBe("Cannot be negative");
  });

  it("accepts no cooldown at all", () => {
    expect(validatePosting(valid({ cooldownDays: null }))).toEqual({});
  });
});

describe("questions", () => {
  it("rejects a blank question", () => {
    const errors = validatePosting(withQuestions(choice({ label: "  " })));
    expect(errors[questionKey("q1", "label")]).toBe("Question is required");
  });

  it("rejects a choice question with no options", () => {
    const errors = validatePosting(withQuestions(choice({ options: [] })));
    expect(errors[questionKey("q1", "options")]).toBe(
      "Add at least one option",
    );
  });

  it("rejects a blank option, naming its position", () => {
    const errors = validatePosting(
      withQuestions(choice({ options: ["Yes", ""] })),
    );
    expect(errors[optionKey("q1", 1)]).toBe("Option cannot be blank");
    expect(errors[optionKey("q1", 0)]).toBeUndefined();
  });

  it("rejects a duplicate option, pointing at the one it copies", () => {
    // Options are matched by text, so two that read the same are one option
    // wearing two rows -- every rule on either fires for both.
    const errors = validatePosting(
      withQuestions(choice({ options: ["Yes", "No", "Yes"] })),
    );
    expect(errors[optionKey("q1", 2)]).toBe("Duplicate of option 1");
    expect(errors[optionKey("q1", 0)]).toBeUndefined();
  });

  it.each([0, 3])("rejects maxSelections %i against two options", (n) => {
    const errors = validatePosting(
      withQuestions(choice({ type: "multi_choice", maxSelections: n })),
    );
    expect(errors[questionKey("q1", "maxSelections")]).toBe(
      "Must be between 1 and 2",
    );
  });

  it("accepts maxSelections at both ends of the range", () => {
    [1, 2].forEach((n) => {
      expect(
        validatePosting(
          withQuestions(choice({ type: "multi_choice", maxSelections: n })),
        ),
      ).toEqual({});
    });
  });

  it.each(["maxLength"])("rejects %s of 0", (field) => {
    const errors = validatePosting(
      withQuestions({ id: "q1", type: "long_text", label: "Why?", [field]: 0 }),
    );
    expect(errors[questionKey("q1", field)]).toBe("Must be between 1 and 5000");
  });

  it("rejects a long text with no character budget", () => {
    const errors = validatePosting(
      withQuestions({ id: "q1", type: "long_text", label: "Why?" }),
    );
    expect(errors[questionKey("q1", "maxLength")]).toBe(
      "Max characters is required",
    );
  });

  it("rejects a budget past the hard ceiling", () => {
    const errors = validatePosting({
      title: "Engineer",
      formSchema: {
        questions: [
          { id: "q1", type: "long_text", label: "Why", maxLength: 5001 },
        ],
      },
    });
    expect(errors["q:q1:maxLength"]).toBe("Must be between 1 and 5000");
  });

  it("accepts a budget of exactly the hard ceiling", () => {
    const errors = validatePosting({
      title: "Engineer",
      formSchema: {
        questions: [
          { id: "q1", type: "long_text", label: "Why", maxLength: 5000 },
        ],
      },
    });
    expect(errors["q:q1:maxLength"]).toBeUndefined();
  });

  it("rejects a blank exact_text expected value", () => {
    const errors = validatePosting(
      withQuestions({ id: "q1", type: "exact_text", label: "Type I AGREE" }),
    );
    expect(errors[questionKey("q1", "expectedValue")]).toBe(
      "Expected value is required",
    );
  });

  it("rejects a rule left pointing at a removed question", () => {
    const errors = validatePosting(
      withQuestions({
        id: "q2",
        type: "short_text",
        label: "Which visa?",
        showWhen: { questionId: "gone", equals: "Yes" },
      }),
    );
    expect(errors[questionKey("q2", "showWhen")]).toBe(
      "Shown by a question that no longer exists",
    );
  });

  it("accepts a rule whose question is present", () => {
    expect(
      validatePosting(
        withQuestions(choice(), {
          id: "q2",
          type: "short_text",
          label: "Which visa?",
          showWhen: { questionId: "q1", equals: "Yes" },
        }),
      ),
    ).toEqual({});
  });
});

describe("screen rules", () => {
  const answerRule = (condition) => ({
    id: "r1",
    action: "reject",
    condition: { source: "answer", operator: "equals", ...condition },
  });

  it("rejects blank email domains", () => {
    const draft = valid({
      screenRules: {
        rules: [
          {
            id: "r1",
            action: "reject",
            condition: {
              source: "email_domain",
              operator: "not_in",
              value: ["  "],
            },
          },
        ],
      },
    });
    expect(validatePosting(draft)[ruleKey("r1", "value")]).toBe(
      "Enter at least one domain",
    );
  });

  it("rejects an email domain rule with no domains at all", () => {
    // A freshly added rule, and a rule whose last tag was removed, are both
    // an empty list now — the shape the editor never used to produce.
    const draft = valid({
      screenRules: {
        rules: [
          {
            id: "r1",
            action: "reject",
            condition: { source: "email_domain", operator: "in", value: [] },
          },
        ],
      },
    });
    expect(validatePosting(draft)[ruleKey("r1", "value")]).toBe(
      "Enter at least one domain",
    );
  });

  it("rejects an answer rule with no question picked", () => {
    const draft = valid({
      formSchema: { questions: [choice()] },
      screenRules: { rules: [answerRule({ questionId: "", value: "" })] },
    });
    expect(validatePosting(draft)[ruleKey("r1", "questionId")]).toBe(
      "Pick a question",
    );
  });

  it("rejects an answer rule whose question was removed", () => {
    const draft = valid({
      formSchema: { questions: [choice()] },
      screenRules: {
        rules: [answerRule({ questionId: "gone", value: "Yes" })],
      },
    });
    expect(validatePosting(draft)[ruleKey("r1", "questionId")]).toBe(
      "This question no longer exists",
    );
  });

  it("asks for a value before complaining it is not an option", () => {
    // A freshly added rule is blank; reporting `""` as not an option reads
    // like a bug rather than something the author has not finished.
    const draft = valid({
      formSchema: { questions: [choice()] },
      screenRules: { rules: [answerRule({ questionId: "q1", value: "" })] },
    });
    expect(validatePosting(draft)[ruleKey("r1", "value")]).toBe("Pick a value");
  });

  it("rejects a value that is not one of the question's options", () => {
    // What renaming an option leaves behind: renameOption rewrites showWhen,
    // but nothing rewrites the screen rules.
    const draft = valid({
      formSchema: { questions: [choice()] },
      screenRules: { rules: [answerRule({ questionId: "q1", value: "Nope" })] },
    });
    expect(validatePosting(draft)[ruleKey("r1", "value")]).toBe(
      '"Nope" is not an option of "Need sponsorship?"',
    );
  });

  it("accepts a rule that names a real option", () => {
    const draft = valid({
      formSchema: { questions: [choice()] },
      screenRules: { rules: [answerRule({ questionId: "q1", value: "No" })] },
    });
    expect(validatePosting(draft)).toEqual({});
  });
});

describe("key helpers", () => {
  it("keeps every field of every question distinct", () => {
    // The components render from these keys and the tests assert on them; a
    // collision would silently merge two fields' errors into one.
    const keys = [
      basicsKey("title"),
      basicsKey("cooldownDays"),
      questionKey("q1", "label"),
      questionKey("q1", "options"),
      questionKey("q2", "label"),
      optionKey("q1", 0),
      optionKey("q1", 1),
      optionKey("q2", 0),
      ruleKey("r1", "value"),
      ruleKey("r1", "questionId"),
      ruleKey("r2", "value"),
    ];
    expect(new Set(keys).size).toBe(keys.length);
  });
});
