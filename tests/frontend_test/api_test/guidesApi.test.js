import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "@/utils/request";
import { listGuideProgress, recordGuideProgress } from "@/api/guidesApi";

vi.mock("@/utils/request", () => ({
  default: { get: vi.fn(), put: vi.fn() },
}));

describe("guidesApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists the caller's guide progress and unwraps the envelope", async () => {
    // Two rows with different keys and statuses, as the backend returns them.
    const rows = [
      {
        guideKey: "welcome",
        status: "snoozed",
        snoozeCount: 1,
        updatedAt: "2026-11-05T09:00:00Z",
      },
      {
        guideKey: "inbox-intro",
        status: "completed",
        snoozeCount: 0,
        updatedAt: "2026-11-06T10:30:00Z",
      },
    ];
    request.get.mockResolvedValue({
      success: true,
      message: "Guide progress fetched.",
      data: rows,
    });

    await expect(listGuideProgress()).resolves.toEqual(rows);
    expect(request.get).toHaveBeenCalledWith("/guides/progress");
  });

  it("records how a guide ended and returns the stored row", async () => {
    const row = {
      guideKey: "welcome",
      status: "dismissed",
      snoozeCount: 2,
      updatedAt: "2026-11-07T08:00:00Z",
    };
    request.put.mockResolvedValue({
      success: true,
      message: "Guide progress saved.",
      data: row,
    });

    await expect(recordGuideProgress("welcome", "snoozed")).resolves.toEqual(
      row,
    );
    expect(request.put).toHaveBeenCalledWith("/guides/progress/welcome", {
      status: "snoozed",
    });
  });
});
