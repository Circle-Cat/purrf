import { describe, expect, it } from "vitest";
import {
  LONG_TEXT_MAX_LENGTH,
  SHORT_TEXT_MAX_LENGTH,
  textBudget,
} from "@/pages/Recruiting/postings/questionLimits";

describe("questionLimits", () => {
  it("mirrors the Python ceilings", () => {
    // Pinned, not derived: job_config_dto.py carries the same two numbers.
    expect(SHORT_TEXT_MAX_LENGTH).toBe(255);
    expect(LONG_TEXT_MAX_LENGTH).toBe(5000);
  });

  it("gives short text the hard ceiling, which its author did not choose", () => {
    expect(textBudget({ type: "short_text" })).toEqual({
      cap: 255,
      explicit: false,
    });
  });

  it("gives long text the author's budget when there is one", () => {
    expect(textBudget({ type: "long_text", maxLength: 200 })).toEqual({
      cap: 200,
      explicit: true,
    });
  });

  it("falls back to the ceiling when the author set no budget", () => {
    expect(textBudget({ type: "long_text" })).toEqual({
      cap: 5000,
      explicit: false,
    });
    expect(textBudget({ type: "long_text", maxLength: null })).toEqual({
      cap: 5000,
      explicit: false,
    });
  });

  it("has nothing to say about a question that is not text", () => {
    expect(textBudget({ type: "multi_choice" })).toBeNull();
    expect(textBudget({ type: "exact_text" })).toBeNull();
    // A question predating the type field, and a missing question.
    expect(textBudget({})).toBeNull();
    expect(textBudget(undefined)).toBeNull();
  });
});
