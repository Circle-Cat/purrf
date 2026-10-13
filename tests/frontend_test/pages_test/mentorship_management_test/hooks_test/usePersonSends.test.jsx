import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { usePersonSends } from "@/pages/MentorshipManagement/hooks/usePersonSends";
import { listPersonSends } from "@/api/mentorshipEmailApi";

vi.mock("@/api/mentorshipEmailApi", () => ({
  listPersonSends: vi.fn(),
  markNotified: vi.fn(),
}));

const sendOf = (sendId, stage) => ({
  sendId,
  stage,
  subject: `Subject ${sendId}`,
  delivered: true,
  reason: null,
  at: "2026-10-12T16:00:00Z",
});

describe("usePersonSends", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the person's sends in the round", async () => {
    listPersonSends.mockResolvedValue([sendOf(14, "match_result")]);
    const { result } = renderHook(() => usePersonSends("7", "3104"));

    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(listPersonSends).toHaveBeenCalledWith("7", "3104");
    expect(result.current[0].sendId).toBe(14);
  });

  it("fetches nothing without a round", () => {
    const { result } = renderHook(() => usePersonSends(null, "3104"));
    expect(listPersonSends).not.toHaveBeenCalled();
    expect(result.current).toEqual([]);
  });

  it("fetches again for another person, dropping the last one's", async () => {
    listPersonSends.mockResolvedValueOnce([sendOf(14, "match_result")]);
    listPersonSends.mockResolvedValueOnce([sendOf(15, "admission")]);
    const { result, rerender } = renderHook(
      ({ userId }) => usePersonSends("7", userId),
      { initialProps: { userId: "3104" } },
    );
    await waitFor(() => expect(result.current[0]?.sendId).toBe(14));

    rerender({ userId: "3105" });
    await waitFor(() => expect(result.current[0]?.sendId).toBe(15));
    expect(listPersonSends).toHaveBeenLastCalledWith("7", "3105");
  });

  it("logs a failed load and shows nothing", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    listPersonSends.mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => usePersonSends("7", "3104"));

    await waitFor(() => expect(error).toHaveBeenCalled());
    expect(result.current).toEqual([]);
    error.mockRestore();
  });
});
