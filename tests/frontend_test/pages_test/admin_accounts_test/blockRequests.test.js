import { describe, it, expect } from "vitest";
import { blockRequestOutcome } from "@/pages/AdminAccounts/utils/blockRequests";

describe("blockRequests", () => {
  it("names each way a block request can be closed", () => {
    expect(blockRequestOutcome("approved")).toBe("Approved");
    expect(blockRequestOutcome("rejected")).toBe("Rejected");
    expect(blockRequestOutcome("withdrawn")).toBe("Withdrawn");
    expect(blockRequestOutcome("superseded")).toBe("Closed by a direct block");
    expect(blockRequestOutcome("someday")).toBe("someday");
  });
});
