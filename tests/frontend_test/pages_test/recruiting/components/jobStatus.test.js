import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { describe, it, expect } from "vitest";
import {
  JOB_STATUSES,
  OPERABLE_STATUSES,
  PENDING_HEADLINE,
  BASE_STATE,
  BASE_TERM,
  ACTION_TERM,
} from "@/pages/Recruiting/components/jobStatus";
import { GLOSSARY } from "@/pages/Recruiting/components/glossary";

// Contract shared with shared_enum_vectors_test.py, which pins this same file
// to JobStatus. Read through node rather than imported, so the fixture stays
// outside vite's root; the path is relative to the vitest working directory.
const STATUSES = JSON.parse(
  readFileSync(
    path.resolve(process.cwd(), "../shared/job_statuses.json"),
    "utf-8",
  ),
);

describe("job status coverage", () => {
  it("mirrors the shared status vector", () => {
    expect(JOB_STATUSES).toEqual(STATUSES);
  });

  it("puts every status in exactly one of operable or pending", () => {
    for (const status of STATUSES) {
      const operable = OPERABLE_STATUSES.includes(status);
      const pending = Object.hasOwn(PENDING_HEADLINE, status);
      expect(
        operable !== pending,
        `"${status}" is ${operable && pending ? "in both" : "in neither"}`,
      ).toBe(true);
    }
  });

  it("gives every pending status a non-empty headline", () => {
    for (const [status, headline] of Object.entries(PENDING_HEADLINE)) {
      expect(headline, `"${status}" has no headline`).toBeTruthy();
    }
  });

  it("resolves every status to a base state and a badge term", () => {
    for (const status of STATUSES) {
      expect(BASE_STATE[status], `"${status}" has no base state`).toBeTruthy();
      expect(
        GLOSSARY[BASE_TERM[status]],
        `"${status}" has no base badge term`,
      ).toBeDefined();
    }
  });

  it("gives draft and a draft under review different explanations", () => {
    expect(BASE_TERM.draft).not.toBe(BASE_TERM.pending_review);
    expect(GLOSSARY[BASE_TERM.draft].label).toBe("Draft");
    expect(GLOSSARY[BASE_TERM.pending_review].label).toBe("Draft");
    expect(GLOSSARY[BASE_TERM.draft].hint).not.toMatch(/can ?not edit/i);
    expect(GLOSSARY[BASE_TERM.pending_review].hint).toMatch(/can ?not edit/i);
  });

  it("gives every pending status its own action-badge term", () => {
    for (const status of Object.keys(PENDING_HEADLINE)) {
      expect(
        GLOSSARY[ACTION_TERM[status]],
        `"${status}" has no action term`,
      ).toBeDefined();
    }
  });
});
