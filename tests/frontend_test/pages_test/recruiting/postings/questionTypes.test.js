import { describe, it, expect } from "vitest";
import {
  QUESTION_TYPES,
  nextQuestionId,
  blankQuestion,
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
      "Short text", "Long text", "Single choice", "Multi choice", "Exact text",
    ]);
  });

  it("generates a unique id past the max existing suffix", () => {
    expect(nextQuestionId([])).toBe("q1");
    expect(nextQuestionId([{ id: "q1" }, { id: "q3" }])).toBe("q4");
  });

  it("blankQuestion seeds choice types with an empty options array", () => {
    expect(blankQuestion("short_text", [])).toEqual({
      id: "q1",
      type: "short_text",
      label: "",
      required: false,
    });
    expect(blankQuestion("single_choice", [{ id: "q1" }])).toEqual({
      id: "q2",
      type: "single_choice",
      label: "",
      required: false,
      options: [],
    });
    expect(blankQuestion("multi_choice", []).options).toEqual([]);
  });
});
