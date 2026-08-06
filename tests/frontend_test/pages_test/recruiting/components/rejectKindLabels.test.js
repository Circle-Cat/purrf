import { describe, it, expect } from "vitest";
import {
  REJECT_KIND_LABEL,
  rejectKindLabel,
} from "@/pages/Recruiting/components/rejectKindLabels";

describe("rejectKindLabel", () => {
  it("returns the specific label for every known JobReviewKind", () => {
    expect(rejectKindLabel("initial")).toBe("Initial submission rejected");
    expect(rejectKindLabel("revision")).toBe("Revision rejected");
    expect(rejectKindLabel("close")).toBe("Close request rejected");
    expect(rejectKindLabel("reopen")).toBe("Reopen request rejected");
  });

  it("covers exactly the four known kinds, so a new backend kind is caught here", () => {
    expect(Object.keys(REJECT_KIND_LABEL)).toEqual([
      "initial",
      "revision",
      "close",
      "reopen",
    ]);
  });

  it("falls back to 'Sent back' for an unknown kind", () => {
    expect(rejectKindLabel("some_future_kind")).toBe("Sent back");
  });

  it("falls back to 'Sent back' for a missing kind", () => {
    expect(rejectKindLabel(null)).toBe("Sent back");
    expect(rejectKindLabel(undefined)).toBe("Sent back");
  });
});
