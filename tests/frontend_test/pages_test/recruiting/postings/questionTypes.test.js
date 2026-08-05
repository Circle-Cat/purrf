import { describe, it, expect } from "vitest";
import {
  QUESTION_TYPES,
  nextQuestionId,
  addQuestion,
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

  it("preserves other schema keys", () => {
    const next = addQuestion({ questions: [], someFutureKey: 1 }, "short_text");
    expect(next.someFutureKey).toBe(1);
  });
});
