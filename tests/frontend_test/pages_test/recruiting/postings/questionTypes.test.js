import { describe, it, expect } from "vitest";
import {
  QUESTION_TYPES,
  nextQuestionId,
  addQuestion,
  revealedBy,
  revealQuestion,
  clearCondition,
  addOption,
  renameOption,
  removeOption,
} from "@/pages/Recruiting/postings/questionTypes";

describe("questionTypes", () => {
  it("lists the five types in order", () => {
    expect(QUESTION_TYPES.map((t) => t.value)).toEqual([
      "short_text",
      "long_text",
      "single_choice",
      "multi_choice",
      "exact_text",
    ]);
    expect(QUESTION_TYPES.map((t) => t.label)).toEqual([
      "Short text",
      "Long text",
      "Single choice",
      "Multi choice",
      "Exact text",
    ]);
  });
});

describe("nextQuestionId", () => {
  it("starts at q1 for an empty form", () => {
    expect(nextQuestionId({ questions: [] })).toBe("q1");
  });

  it("derives from the live ids when there is no counter yet", () => {
    expect(nextQuestionId({ questions: [{ id: "q1" }, { id: "q4" }] })).toBe(
      "q5",
    );
  });

  it("uses the persisted counter when it is ahead of the live ids", () => {
    expect(nextQuestionId({ questions: [{ id: "q1" }], nextSeq: 9 })).toBe(
      "q9",
    );
  });

  it("never returns an id already in use, even with a stale counter", () => {
    expect(
      nextQuestionId({ questions: [{ id: "q1" }, { id: "q4" }], nextSeq: 2 }),
    ).toBe("q5");
  });
});

describe("addQuestion", () => {
  it("appends the question and advances the counter", () => {
    const next = addQuestion({ questions: [], nextSeq: 1 }, "short_text");
    expect(next.questions).toEqual([
      { id: "q1", type: "short_text", label: "", required: false },
    ]);
    expect(next.nextSeq).toBe(2);
  });

  it("seeds an empty options array for a choice type", () => {
    const next = addQuestion({ questions: [] }, "multi_choice");
    expect(next.questions[0].options).toEqual([]);
  });

  it("does not recycle an id after a delete", () => {
    let schema = addQuestion(
      addQuestion({ questions: [] }, "short_text"),
      "short_text",
    );
    expect(schema.questions.map((q) => q.id)).toEqual(["q1", "q2"]);
    schema = { ...schema, questions: schema.questions.slice(0, 1) };
    schema = addQuestion(schema, "short_text");
    expect(schema.questions.map((q) => q.id)).toEqual(["q1", "q3"]);
  });

  // The budget is required, so a long text that arrived without one would
  // start life carrying an error the author never caused. 300 is asserted as a
  // literal rather than through the exported constant: importing it would make
  // the assertion pass vacuously if the constant were ever removed.
  it("gives a new long text the default character budget", () => {
    const next = addQuestion({ questions: [] }, "long_text");
    expect(next.questions[0].maxLength).toBe(300);
  });

  it("gives no character budget to a short text", () => {
    const next = addQuestion({ questions: [] }, "short_text");
    expect(next.questions[0]).not.toHaveProperty("maxLength");
  });

  it("preserves other schema keys", () => {
    const next = addQuestion({ questions: [], someFutureKey: 1 }, "short_text");
    expect(next.someFutureKey).toBe(1);
  });
});

/** A car question with two options, "Yes" revealing q2 and q3. */
const revealSchema = () => ({
  nextSeq: 4,
  questions: [
    {
      id: "q1",
      type: "single_choice",
      label: "Car?",
      options: ["Yes", "No"],
    },
    {
      id: "q2",
      type: "short_text",
      label: "Model",
      showWhen: { questionId: "q1", equals: "Yes" },
    },
    {
      id: "q3",
      type: "short_text",
      label: "Year",
      showWhen: { questionId: "q1", equals: "Yes" },
    },
    {
      id: "q4",
      type: "short_text",
      label: "Why not",
      showWhen: { questionId: "q1", equals: "No" },
    },
  ],
});

describe("revealedBy", () => {
  it("returns the questions one option reveals, in form order", () => {
    expect(
      revealedBy(revealSchema().questions, "q1", "Yes").map((q) => q.id),
    ).toEqual(["q2", "q3"]);
  });

  it("does not mix up options of the same question", () => {
    expect(
      revealedBy(revealSchema().questions, "q1", "No").map((q) => q.id),
    ).toEqual(["q4"]);
  });

  it("returns nothing for an option with no rules", () => {
    expect(revealedBy(revealSchema().questions, "q1", "Maybe")).toEqual([]);
  });
});

describe("revealQuestion", () => {
  it("writes the rule onto the question being revealed", () => {
    const next = revealQuestion(
      { questions: [{ id: "q1" }, { id: "q2" }] },
      "q2",
      "q1",
      "Yes",
    );
    expect(next.questions[1].showWhen).toEqual({
      questionId: "q1",
      equals: "Yes",
    });
    // The choice question itself records nothing.
    expect(next.questions[0]).toEqual({ id: "q1" });
  });

  it("moves an already-revealed question instead of adding a second rule", () => {
    const next = revealQuestion(revealSchema(), "q2", "q1", "No");
    expect(next.questions[1].showWhen).toEqual({
      questionId: "q1",
      equals: "No",
    });
  });
});

describe("clearCondition", () => {
  it("drops the key rather than leaving it undefined", () => {
    const next = clearCondition(revealSchema(), "q2");
    expect("showWhen" in next.questions[1]).toBe(false);
    expect(next.questions[2].showWhen).toBeDefined();
  });
});

describe("addOption", () => {
  it("appends a blank option to the named question only", () => {
    const next = addOption(revealSchema(), "q1");
    expect(next.questions[0].options).toEqual(["Yes", "No", ""]);
  });
});

describe("renameOption", () => {
  // An option is referenced by its text, so a rename that didn't carry the
  // references would leave the revealed questions waiting on text no answer
  // can ever equal.
  it("carries the questions the option reveals", () => {
    const next = renameOption(revealSchema(), "q1", 0, "Yes, I do");
    expect(next.questions[0].options).toEqual(["Yes, I do", "No"]);
    expect(next.questions[1].showWhen.equals).toBe("Yes, I do");
    expect(next.questions[2].showWhen.equals).toBe("Yes, I do");
    // The other option's rule is untouched.
    expect(next.questions[3].showWhen.equals).toBe("No");
  });

  it("only rewrites rules pointing at the renamed question", () => {
    const schema = revealSchema();
    schema.questions.push({
      id: "q5",
      type: "short_text",
      showWhen: { questionId: "q9", equals: "Yes" },
    });
    const next = renameOption(schema, "q1", 0, "Yep");
    expect(next.questions[4].showWhen).toEqual({
      questionId: "q9",
      equals: "Yes",
    });
  });
});

describe("removeOption", () => {
  it("drops the option at the given index", () => {
    const next = removeOption(revealSchema(), "q1", 1);
    expect(next.questions[0].options).toEqual(["Yes"]);
  });

  // The editor blocks removal while any exist, so this is the shape the ops
  // layer is allowed to leave behind, not one a user can reach.
  it("leaves the questions the option revealed alone", () => {
    const next = removeOption(revealSchema(), "q1", 1);
    expect(next.questions[3].showWhen).toEqual({
      questionId: "q1",
      equals: "No",
    });
  });

  it("leaves the other questions' options untouched", () => {
    const schema = revealSchema();
    schema.questions.push({
      id: "q5",
      type: "single_choice",
      label: "Bike?",
      options: ["Yes", "No"],
    });
    const next = removeOption(schema, "q1", 0);
    expect(next.questions[4].options).toEqual(["Yes", "No"]);
  });
});
