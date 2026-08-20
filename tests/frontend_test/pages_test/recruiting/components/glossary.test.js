import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { describe, it, expect } from "vitest";
import {
  GLOSSARY,
  stageTermId,
  lockReasonText,
  APPLICATION_STAGES,
  APPLICATION_LOCK_REASONS,
} from "@/pages/Recruiting/components/glossary";

// Read through node rather than imported, so the fixture stays outside vite's
// root and needs no resolver configuration; the path is relative to the vitest
// working directory (tests/frontend_test).
const STAGES = JSON.parse(
  readFileSync(
    path.resolve(process.cwd(), "../shared/application_stages.json"),
    "utf-8",
  ),
);

const LOCK_REASONS = JSON.parse(
  readFileSync(
    path.resolve(process.cwd(), "../shared/application_lock_reasons.json"),
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

  // Only the badge on a non-clickable row gets a term. The Confirmed/Pending
  // badges sit inside a row that is itself a Link, where a focusable trigger
  // would nest one control in another -- the same reason the postings list
  // leaves its status badge inert.
  it("holds the term the interviewer's queue renders", () => {
    expect(GLOSSARY["evaluation.no_longer_assigned"]).toBeDefined();
  });

  // The three conditions ApplicationService._lock_reason tests, said once in
  // the recruiter's words.
  it("tells the recruiter that a status move locks the candidate out", () => {
    const { hint } = GLOSSARY["application.edit_lock"];

    expect(hint).toContain("Moving off Pending");
    expect(hint).toContain("advancing the stage");
    expect(hint).toContain("confirming an evaluation");
    expect(hint).toContain("one-way");
  });
});

describe("lockReasonText", () => {
  it("mirrors the shared lock-reason vector", () => {
    expect(APPLICATION_LOCK_REASONS).toEqual(LOCK_REASONS);
  });

  it("has wording for every reason the backend can send", () => {
    for (const reason of LOCK_REASONS) {
      expect(
        lockReasonText(reason, "Recruiter screening"),
        `no wording for lock reason "${reason}"`,
      ).toBeTruthy();
    }
  });

  it("names the stage the application moved to", () => {
    expect(lockReasonText("advanced", "Tech")).toBe(
      "It moved to Tech, so it can't be edited any more.",
    );
  });

  it("still says something when the stage label is unknown", () => {
    expect(lockReasonText("advanced", null)).toBe(
      "It moved on, so it can't be edited any more.",
    );
  });

  it("does not expose which internal condition started the review", () => {
    expect(lockReasonText("in_review", "Recruiter screening")).toBe(
      "A recruiter has started reviewing it, so it can't be edited any more.",
    );
  });

  it("tells the candidate the posting itself closed", () => {
    expect(lockReasonText("closed", "Recruiter screening")).toBe(
      "This posting has closed, so it can't be edited any more.",
    );
  });

  it("returns null for no reason, so an editable application renders nothing", () => {
    expect(lockReasonText(null, "Tech")).toBeNull();
    expect(lockReasonText("not_a_reason", "Tech")).toBeNull();
  });
});
