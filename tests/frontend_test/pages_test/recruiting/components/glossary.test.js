import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { describe, it, expect } from "vitest";
import {
  GLOSSARY,
  stageTermId,
  APPLICATION_STAGES,
} from "@/pages/Recruiting/components/glossary";

// Contract shared with application_stages_vector_test.py, which pins this same
// file to ApplicationStage. Read through node rather than imported, so the
// fixture stays outside vite's root and needs no resolver configuration; the
// path is relative to the vitest working directory (tests/frontend_test).
const STAGES = JSON.parse(
  readFileSync(
    path.resolve(process.cwd(), "../shared/application_stages.json"),
    "utf-8",
  ),
);

describe("glossary", () => {
  it("mirrors the shared stage vector", () => {
    expect(APPLICATION_STAGES).toEqual(STAGES);
  });

  it("resolves every stage on an employment posting to an existing term", () => {
    for (const stage of STAGES) {
      const id = stageTermId(stage, "employment");
      expect(
        GLOSSARY[id],
        `no glossary term for employment stage "${stage}"`,
      ).toBeDefined();
    }
  });

  it("resolves every stage on an activity posting to an existing term", () => {
    for (const stage of STAGES) {
      const id = stageTermId(stage, "activity");
      expect(
        GLOSSARY[id],
        `no glossary term for activity stage "${stage}"`,
      ).toBeDefined();
    }
  });

  it("presents a hired applicant on an activity posting as Admitted", () => {
    expect(GLOSSARY[stageTermId("hired", "activity")].label).toBe("Admitted");
    expect(GLOSSARY[stageTermId("hired", "employment")].label).toBe("Hired");
  });

  it("gives every term a non-empty label and hint", () => {
    for (const [id, term] of Object.entries(GLOSSARY)) {
      expect(term.label, `${id} has no label`).toBeTruthy();
      expect(term.hint, `${id} has no hint`).toBeTruthy();
    }
  });

  it("returns null for an unknown stage rather than throwing", () => {
    expect(stageTermId("not_a_stage", "employment")).toBeNull();
  });
});
