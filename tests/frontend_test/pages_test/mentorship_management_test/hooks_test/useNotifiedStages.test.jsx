import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useNotifiedStages } from "@/pages/MentorshipManagement/hooks/useNotifiedStages";
import { listNotifiedStages } from "@/api/mentorshipEmailApi";

vi.mock("@/api/mentorshipEmailApi", () => ({
  listNotifiedStages: vi.fn(),
  markNotified: vi.fn(),
}));

describe("useNotifiedStages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("maps each person to the stages sent to them in the round", async () => {
    listNotifiedStages.mockResolvedValue([
      { userId: 11, stages: ["round_recruitment", "admission"] },
      { userId: 12, stages: ["midterm_reminder"] },
    ]);
    const { result } = renderHook(() => useNotifiedStages("7"));

    await waitFor(() => expect(result.current.stagesByUser.size).toBe(2));
    expect(listNotifiedStages).toHaveBeenCalledWith("7");
    expect(result.current.stagesByUser.get(11)).toEqual([
      { stage: "round_recruitment", scheduledAt: null },
      { stage: "admission", scheduledAt: null },
    ]);
    expect(result.current.stagesByUser.get(12)).toEqual([
      { stage: "midterm_reminder", scheduledAt: null },
    ]);
  });

  it("keeps a stage sent before and scheduled again as both, sent first", async () => {
    listNotifiedStages.mockResolvedValue([
      {
        userId: 11,
        stages: ["admission", "match_result"],
        scheduled: [
          { stage: "match_result", sendAt: "2026-10-12T16:00:00Z" },
          { stage: "midterm_reminder", sendAt: "2026-11-02T17:30:00Z" },
        ],
      },
      {
        userId: 12,
        stages: [],
        scheduled: [
          { stage: "final_followup", sendAt: "2026-12-01T18:00:00Z" },
        ],
      },
    ]);
    const { result } = renderHook(() => useNotifiedStages("7"));

    await waitFor(() => expect(result.current.stagesByUser.size).toBe(2));
    expect(result.current.stagesByUser.get(11)).toEqual([
      { stage: "admission", scheduledAt: null },
      { stage: "match_result", scheduledAt: null },
      { stage: "match_result", scheduledAt: "2026-10-12T16:00:00Z" },
      { stage: "midterm_reminder", scheduledAt: "2026-11-02T17:30:00Z" },
    ]);
    expect(result.current.stagesByUser.get(12)).toEqual([
      { stage: "final_followup", scheduledAt: "2026-12-01T18:00:00Z" },
    ]);
  });

  it("fetches nothing without a round", () => {
    const { result } = renderHook(() => useNotifiedStages(null));
    expect(listNotifiedStages).not.toHaveBeenCalled();
    expect(result.current.stagesByUser.size).toBe(0);
  });

  it("fetches again when the round changes", async () => {
    listNotifiedStages.mockResolvedValueOnce([
      { userId: 11, stages: ["admission"] },
    ]);
    listNotifiedStages.mockResolvedValueOnce([
      { userId: 12, stages: ["midterm_reminder"] },
    ]);
    const { result, rerender } = renderHook(
      ({ roundId }) => useNotifiedStages(roundId),
      { initialProps: { roundId: "7" } },
    );
    await waitFor(() => expect(result.current.stagesByUser.has(11)).toBe(true));

    rerender({ roundId: "3" });
    await waitFor(() => expect(result.current.stagesByUser.has(12)).toBe(true));
    expect(result.current.stagesByUser.has(11)).toBe(false);
    expect(listNotifiedStages).toHaveBeenLastCalledWith("3");
  });

  it("adds stages marked by hand after the sent ones, and lets Kit's own win", async () => {
    listNotifiedStages.mockResolvedValue([
      {
        userId: 11,
        stages: ["admission"],
        scheduled: [
          { stage: "midterm_reminder", sendAt: "2026-11-02T17:30:00Z" },
        ],
        manual: ["admission", "match_result"],
      },
    ]);
    const { result } = renderHook(() => useNotifiedStages("7"));

    await waitFor(() => expect(result.current.stagesByUser.size).toBe(1));
    expect(result.current.stagesByUser.get(11)).toEqual([
      { stage: "admission", scheduledAt: null },
      { stage: "match_result", scheduledAt: null, manual: true },
      { stage: "midterm_reminder", scheduledAt: "2026-11-02T17:30:00Z" },
    ]);
  });

  it("reloads in place", async () => {
    listNotifiedStages.mockResolvedValueOnce([]);
    listNotifiedStages.mockResolvedValueOnce([
      { userId: 11, stages: ["admission"] },
    ]);
    const { result } = renderHook(() => useNotifiedStages("7"));
    await waitFor(() => expect(listNotifiedStages).toHaveBeenCalledTimes(1));

    await act(() => result.current.reload());
    expect(result.current.stagesByUser.get(11)).toEqual([
      { stage: "admission", scheduledAt: null },
    ]);
  });

  it("logs a failed load and shows nothing", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    listNotifiedStages.mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => useNotifiedStages("7"));

    await waitFor(() => expect(error).toHaveBeenCalled());
    expect(result.current.stagesByUser.size).toBe(0);
    error.mockRestore();
  });
});
