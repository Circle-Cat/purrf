import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useMatchingRun } from "@/pages/MentorshipManagement/hooks/useMatchingRun";
import { getMatchingRun } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  getMatchingRun: vi.fn(),
  getMatchingResults: vi.fn(),
  getMatchingUnmatched: vi.fn(),
}));

describe("useMatchingRun", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the round's run and reloads it in place", async () => {
    getMatchingRun
      .mockResolvedValueOnce({ data: { runId: "run-1", status: "running" } })
      .mockResolvedValueOnce({ data: { runId: "run-1", status: "done" } });
    const { result } = renderHook(() => useMatchingRun("7"));

    await waitFor(() =>
      expect(result.current.overview).toEqual({
        runId: "run-1",
        status: "running",
      }),
    );
    expect(result.current.isLoading).toBe(false);

    await act(async () => {
      await result.current.reload();
    });

    expect(result.current.overview).toEqual({
      runId: "run-1",
      status: "done",
    });
  });

  it("does not let a reload for the old round overwrite the new round", async () => {
    let resolveStaleReload;
    getMatchingRun
      .mockResolvedValueOnce({ data: { runId: "run-7", status: "done" } })
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveStaleReload = resolve;
        }),
      )
      .mockResolvedValueOnce({ data: { runId: "run-8", status: "running" } });
    const { result, rerender } = renderHook(
      ({ roundId }) => useMatchingRun(roundId),
      { initialProps: { roundId: "7" } },
    );
    await waitFor(() => expect(result.current.overview?.runId).toBe("run-7"));

    let staleReload;
    act(() => {
      staleReload = result.current.reload();
    });
    rerender({ roundId: "8" });
    await waitFor(() => expect(result.current.overview?.runId).toBe("run-8"));

    await act(async () => {
      resolveStaleReload({ data: { runId: "run-7", status: "done" } });
      await staleReload;
    });

    expect(getMatchingRun.mock.calls).toEqual([["7"], ["7"], ["8"]]);
    expect(result.current.overview).toEqual({
      runId: "run-8",
      status: "running",
    });
  });

  it("stops loading when a reload overtakes the round's own load", async () => {
    let resolveFirstLoad;
    getMatchingRun
      .mockReturnValueOnce(
        new Promise((resolve) => {
          resolveFirstLoad = resolve;
        }),
      )
      .mockResolvedValueOnce({ data: { runId: "run-7", status: "done" } });
    const { result } = renderHook(() => useMatchingRun("7"));
    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      await result.current.reload();
    });
    await act(async () => {
      resolveFirstLoad({ data: { runId: "run-7", status: "running" } });
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.overview).toEqual({
      runId: "run-7",
      status: "done",
    });
  });
});
