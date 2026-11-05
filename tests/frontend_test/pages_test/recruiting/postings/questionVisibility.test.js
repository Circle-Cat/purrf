import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { describe, it, expect } from "vitest";
import {
  pruneAnswers,
  visibleQuestions,
} from "@/pages/Recruiting/postings/questionVisibility";

// Contract shared with form_visibility_test.py. See the fixture's own comment:
// the server deletes the answers to every question this module leaves out, so
// both implementations are held to one definition of the rule rather than to
// each other's docstrings. Read through node rather than imported, so the file
// stays outside vite's root and needs no resolver configuration; the path is
// relative to the vitest working directory (tests/frontend_test).
const VECTORS = JSON.parse(
  readFileSync(
    path.resolve(process.cwd(), "../shared/form_visibility_vectors.json"),
    "utf-8",
  ),
);

// `null` rather than `undefined` for a question with no id, because the
// fixture is JSON and Python reads the same slot as `None`.
const visibleIds = (questions, answers) =>
  visibleQuestions(questions, answers).map((q) => q.id ?? null);

describe("shared visibility vectors", () => {
  it("loaded the fixture", () => {
    // A path typo would otherwise turn the whole contract into a no-op.
    expect(VECTORS.cases.length).toBeGreaterThanOrEqual(24);
  });

  it("names every case distinctly", () => {
    // Two cases carrying the same name once hid the fact that they were the
    // same case, which reads as coverage the fixture does not have.
    const names = VECTORS.cases.map((c) => c.name);
    expect(new Set(names).size).toBe(names.length);
  });

  it.each(VECTORS.cases)(
    "visible set: $name",
    ({ questions, answers, visible }) => {
      expect(visibleIds(questions, answers)).toEqual(visible);
    },
  );

  it.each(VECTORS.cases)(
    "kept answers: $name",
    ({ questions, answers, pruned }) => {
      expect(pruneAnswers(questions, answers)).toEqual(pruned);
    },
  );

  it.each(VECTORS.cases)(
    "pruning twice changes nothing: $name",
    ({ questions, answers, pruned }) => {
      // The renderer resolves visibility against whatever the last write
      // stored, so this side has to be as stable under repetition as the
      // server is. Asserted against the vector rather than against the first
      // pass, so an implementation that prunes nothing cannot satisfy it.
      expect(pruneAnswers(questions, pruneAnswers(questions, answers))).toEqual(
        pruned,
      );
    },
  );
});

describe("visibleQuestions", () => {
  it("is always true without a showWhen rule", () => {
    expect(visibleIds([{ id: "q1" }], {})).toEqual(["q1"]);
  });

  it("hides a question whose gate is itself hidden", () => {
    // q3's rule reads q2's recorded answer, which outlives q2 going hidden.
    // Resolving that rule on its own would render q3 under a gate the
    // candidate can no longer see, and the server would then delete q2's
    // answer and hide q3 on the next save.
    const questions = [
      { id: "q1" },
      { id: "q2", showWhen: { questionId: "q1", equals: "Yes" } },
      { id: "q3", showWhen: { questionId: "q2", equals: "Yes" } },
    ];
    expect(visibleIds(questions, { q1: "No", q2: "Yes" })).toEqual(["q1"]);
  });

  it("resolves a gate declared after the question it gates", () => {
    const questions = [
      { id: "q2", showWhen: { questionId: "q1", equals: "Yes" } },
      { id: "q1" },
    ];
    expect(visibleIds(questions, { q1: "Yes" })).toEqual(["q2", "q1"]);
  });
});
