import { describe, it, expect } from "vitest";
import { humanize, stageLabel } from "@/pages/Recruiting/board/stageFormat";

describe("humanize", () => {
  it("sentence-cases a snake_case value", () => {
    expect(humanize("recruiter_screening")).toBe("Recruiter screening");
    expect(humanize("in_progress")).toBe("In progress");
  });

  it("returns an empty string for null/undefined", () => {
    expect(humanize(null)).toBe("");
    expect(humanize(undefined)).toBe("");
  });
});

describe("stageLabel", () => {
  it("labels hired as Admitted on activity jobs", () => {
    expect(stageLabel("hired", "activity")).toBe("Admitted");
  });

  it("keeps Hired on employment jobs", () => {
    expect(stageLabel("hired", "employment")).toBe("Hired");
  });

  it("falls back to humanize for every other stage/kind combination", () => {
    expect(stageLabel("recruiter_screening", "activity")).toBe(
      "Recruiter screening",
    );
    expect(stageLabel("offer", "employment")).toBe("Offer");
    expect(stageLabel("hired", undefined)).toBe("Hired");
    expect(stageLabel(null, "activity")).toBe("");
  });
});
