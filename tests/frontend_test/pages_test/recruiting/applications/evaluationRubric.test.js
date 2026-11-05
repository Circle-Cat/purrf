import { describe, it, expect } from "vitest";
import {
  RUBRICS,
  rubricFor,
} from "@/pages/Recruiting/applications/evaluationRubric";

describe("rubricFor", () => {
  it("returns the recruiter_screening rubric's 3 sections with the right field counts/ids", () => {
    const sections = rubricFor("recruiter_screening");
    expect(sections).toHaveLength(3);
    expect(sections.map((section) => section.title)).toEqual([
      "Background Fitness",
      "Cultural Fitness",
      "Overall Evaluation",
    ]);
    expect(sections[0].fields.map((field) => field.id)).toEqual([
      "bg_match",
      "bg_consistency",
      "bg_strength",
    ]);
    expect(sections[1].fields.map((field) => field.id)).toEqual([
      "format_compliance",
      "mission_alignment",
      "writing_quality",
    ]);
    expect(sections[2].fields.map((field) => field.id)).toEqual(["overall"]);
  });

  it("returns undefined for a stage with no rubric", () => {
    expect(rubricFor("offer")).toBeUndefined();
  });

  it("returns undefined for an unknown stage", () => {
    expect(rubricFor("not_a_stage")).toBeUndefined();
  });

  describe("exact field id list per stage (snapshot-style)", () => {
    it("recruiter_screening", () => {
      expect(
        RUBRICS.recruiter_screening.map((section) =>
          section.fields.map((field) => field.id),
        ),
      ).toEqual([
        ["bg_match", "bg_consistency", "bg_strength"],
        ["format_compliance", "mission_alignment", "writing_quality"],
        ["overall"],
      ]);
    });

    it("behavioral", () => {
      expect(
        RUBRICS.behavioral.map((section) =>
          section.fields.map((field) => field.id),
        ),
      ).toEqual([
        ["ownership", "communication", "execution_quality"],
        ["prioritization", "growth", "self_development"],
        ["overall"],
      ]);
    });

    it("tech", () => {
      expect(
        RUBRICS.tech.map((section) => section.fields.map((field) => field.id)),
      ).toEqual([
        [
          "data_structures",
          "correctness",
          "debugging",
          "communication_clarity",
        ],
        ["problem_statement", "candidate_approach", "code_snippet"],
        ["overall"],
      ]);
    });

    it("board_review", () => {
      expect(
        RUBRICS.board_review.map((section) =>
          section.fields.map((field) => field.id),
        ),
      ).toEqual([["final_decision"]]);
    });
  });

  describe("field shapes (id/label/valueType/hasNotes verbatim from backend)", () => {
    it("bg_strength has valueType score and hasNotes true", () => {
      const field = RUBRICS.recruiter_screening[0].fields[2];
      expect(field).toEqual({
        id: "bg_strength",
        label: "Background strength",
        valueType: "score",
        hasNotes: true,
      });
    });

    it("bg_match has valueType pass_fail and no hasNotes flag set to true", () => {
      const field = RUBRICS.recruiter_screening[0].fields[0];
      expect(field.valueType).toBe("pass_fail");
      expect(field.hasNotes).toBeFalsy();
    });

    it("problem_statement (tech Interview Record) has valueType notes", () => {
      const field = RUBRICS.tech[1].fields[0];
      expect(field).toEqual({
        id: "problem_statement",
        label: "Problem Statement",
        valueType: "notes",
      });
    });

    it("final_decision (board_review) has valueType pass_fail and hasNotes true", () => {
      const field = RUBRICS.board_review[0].fields[0];
      expect(field).toEqual({
        id: "final_decision",
        label:
          "Should this candidate proceed to the offer stage / be rejected?",
        valueType: "pass_fail",
        hasNotes: true,
      });
    });
  });
});
