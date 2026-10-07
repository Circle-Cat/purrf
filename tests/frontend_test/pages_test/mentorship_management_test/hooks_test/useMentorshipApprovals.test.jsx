import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useMentorshipApprovers } from "@/pages/MentorshipManagement/hooks/useMentorshipApprovers";
import { useMyMentorshipApprovals } from "@/pages/MentorshipManagement/hooks/useMyMentorshipApprovals";
import { useApprovalAction } from "@/pages/MentorshipManagement/hooks/useApprovalAction";
import { act } from "@testing-library/react";
import { toast } from "sonner";
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

describe("useApprovalAction", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(toast, "success").mockImplementation(() => {});
    vi.spyOn(toast, "error").mockImplementation(() => {});
  });

  it("toasts and reloads after a call that succeeds", async () => {
    const onChanged = vi.fn();
    const { result } = renderHook(() => useApprovalAction(onChanged));

    let ok;
    await act(async () => {
      ok = await result.current.act(
        () => Promise.resolve(),
        "Done.",
        "Failed.",
      );
    });

    expect(ok).toBe(true);
    expect(toast.success).toHaveBeenCalledWith("Done.");
    expect(onChanged).toHaveBeenCalled();
    expect(result.current.busy).toBe(false);
  });

  it("shows the server's refusal, or the fallback, and does not reload", async () => {
    const onChanged = vi.fn();
    const { result } = renderHook(() => useApprovalAction(onChanged));

    let ok;
    await act(async () => {
      ok = await result.current.act(
        () =>
          Promise.reject({
            response: { data: { message: "Already closed." } },
          }),
        "Done.",
        "Failed.",
      );
    });
    await act(async () => {
      await result.current.act(
        () => Promise.reject(new Error("x")),
        "Done.",
        "Failed.",
      );
    });

    expect(ok).toBe(false);
    expect(toast.error.mock.calls).toEqual([["Already closed."], ["Failed."]]);
    expect(onChanged).not.toHaveBeenCalled();
  });
});
