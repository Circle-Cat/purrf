import { describe, it, expect } from "vitest";
import { isVisible } from "@/pages/Recruiting/postings/questionVisibility";

describe("isVisible", () => {
  it("matches membership for an array answer", () => {
    const q = { id: "q2", showWhen: { questionId: "q1", equals: "Remote" } };
    expect(isVisible(q, { q1: ["Remote", "Hybrid"] })).toBe(true);
    expect(isVisible(q, { q1: ["On-site"] })).toBe(false);
  });

  it("is always true without a showWhen rule", () => {
    expect(isVisible({ id: "q1" }, {})).toBe(true);
  });
});
