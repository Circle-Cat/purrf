import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useMentorshipApprovers } from "@/pages/MentorshipManagement/hooks/useMentorshipApprovers";
import { useMyMentorshipApprovals } from "@/pages/MentorshipManagement/hooks/useMyMentorshipApprovals";
import {
  getMentorshipApprovers,
  getMyMentorshipApprovals,
} from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  getMentorshipApprovers: vi.fn(),
  getMyMentorshipApprovals: vi.fn(),
}));

describe("useMentorshipApprovers", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads the approvers once enabled", async () => {
    getMentorshipApprovers.mockResolvedValue({
      data: [{ userId: 8, name: "Rae Kim" }],
    });
    const { result, rerender } = renderHook(
      ({ on }) => useMentorshipApprovers(on),
      { initialProps: { on: false } },
    );
    expect(getMentorshipApprovers).not.toHaveBeenCalled();

    rerender({ on: true });

    await waitFor(() =>
      expect(result.current.approvers).toEqual([
        { userId: 8, name: "Rae Kim" },
      ]),
    );
    expect(result.current.error).toBe(false);
  });

  it("reports a failed load", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    getMentorshipApprovers.mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useMentorshipApprovers(true));

    await waitFor(() => expect(result.current.error).toBe(true));
  });
});

describe("useMyMentorshipApprovals", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads my pending requests, and again on reload", async () => {
    getMyMentorshipApprovals.mockResolvedValue({ data: [{ requestId: 31 }] });
    const { result } = renderHook(() => useMyMentorshipApprovals(true));

    await waitFor(() =>
      expect(result.current.requests).toEqual([{ requestId: 31 }]),
    );
    getMyMentorshipApprovals.mockResolvedValue({ data: [] });
    await result.current.reload();

    await waitFor(() => expect(result.current.requests).toEqual([]));
    expect(getMyMentorshipApprovals).toHaveBeenCalledTimes(2);
  });

  it("asks nothing when disabled", () => {
    const { result } = renderHook(() => useMyMentorshipApprovals(false));

    expect(result.current.requests).toEqual([]);
    expect(getMyMentorshipApprovals).not.toHaveBeenCalled();
  });
});
