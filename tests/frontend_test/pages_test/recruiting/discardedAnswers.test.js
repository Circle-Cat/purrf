import { describe, it, expect } from "vitest";
import { discardedAnswers } from "@/pages/Recruiting/discardedAnswers";

const gate = {
  id: "q1",
  type: "single_choice",
  label: "Need sponsorship?",
  options: ["Yes", "No"],
};
const gated = (id, label, on = "q1", equals = "Yes") => ({
  id,
  type: "long_text",
  label,
  showWhen: { questionId: on, equals },
});

/** Just the labels, in the order the dialog would list them. */
const labels = (questions, answers) =>
  discardedAnswers(questions, answers).map((entry) => entry.label);

describe("discardedAnswers", () => {
  it("finds nothing when every answer is still asked for", () => {
    expect(discardedAnswers([gate], { q1: "Yes" })).toEqual([]);
  });

  it("finds nothing on an empty form with no answers", () => {
    expect(discardedAnswers([], {})).toEqual([]);
  });

  it("names the question behind an answer the form stopped showing", () => {
    // The candidate wrote a visa type, then changed their mind about needing
    // sponsorship. Saving deletes the visa type.
    expect(
      labels([gate, gated("q2", "Which visa?")], {
        q1: "No",
        q2: "F-1 OPT",
      }),
    ).toEqual(["Which visa?"]);
  });

  it("names every layer of a chain, not just the one that was flipped", () => {
    // Visibility is transitive, so one flip at the root takes the subtree.
    expect(
      labels(
        [
          gate,
          gated("q2", "Which visa?"),
          gated("q3", "Expiry date?", "q2", "F-1"),
        ],
        { q1: "No", q2: "F-1", q3: "2027-06-01" },
      ),
    ).toEqual(["Which visa?", "Expiry date?"]);
  });

  it("says so when the question is gone from the form entirely", () => {
    expect(labels([gate], { q1: "Yes", q9: "WeChat handle" })).toEqual([
      "A question that is no longer on the form",
    ]);
  });

  it("attributes an orphaned Other free text to its question", () => {
    const choice = {
      id: "q3",
      type: "multi_choice",
      label: "Teams?",
      options: ["Backend", "Other"],
      otherOption: "Other",
    };
    expect(
      labels([choice], { q3: ["Backend"], q3__other: "Infrastructure" }),
    ).toEqual(["Teams? — your own answer"]);
  });

  it("leaves an Other free text alone while the option is still picked", () => {
    const choice = {
      id: "q3",
      type: "multi_choice",
      label: "Teams?",
      options: ["Backend", "Other"],
      otherOption: "Other",
    };
    expect(
      discardedAnswers([choice], {
        q3: ["Backend", "Other"],
        q3__other: "Infrastructure",
      }),
    ).toEqual([]);
  });

  it.each([
    ["", "a blank string"],
    [[], "an empty selection"],
    [null, "null"],
  ])("does not warn about losing %p (%s)", (value) => {
    // The server drops these too, but there is nothing there to mourn, and
    // warning would put a dialog in front of nearly every save.
    expect(
      discardedAnswers([gate, gated("q2", "Which visa?")], {
        q1: "No",
        q2: value,
      }),
    ).toEqual([]);
  });

  it.each([0, false])(
    "does warn about losing the recorded value %p",
    (value) => {
      // Falsy but answered: a rating of 0 or an explicit "no" is a real answer.
      expect(
        labels([gate, gated("q2", "How many years?")], { q1: "No", q2: value }),
      ).toEqual(["How many years?"]);
    },
  );

  it("falls back to the id when a question has no label yet", () => {
    expect(
      labels([gate, { ...gated("q2", ""), label: "" }], {
        q1: "No",
        q2: "typed",
      }),
    ).toEqual(["q2"]);
  });

  it("tolerates a missing form and missing answers", () => {
    expect(discardedAnswers(undefined, undefined)).toEqual([]);
    expect(discardedAnswers(null, { q1: "x" })).toEqual([
      {
        key: "q1",
        value: "x",
        label: "A question that is no longer on the form",
      },
    ]);
  });
});
