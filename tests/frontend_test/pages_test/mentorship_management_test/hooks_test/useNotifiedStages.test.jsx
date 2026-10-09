import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useNotifiedStages } from "@/pages/MentorshipManagement/hooks/useNotifiedStages";
import { listNotifiedStages } from "@/api/mentorshipEmailApi";

vi.mock("@/api/mentorshipEmailApi", () => ({
  listNotifiedStages: vi.fn(),
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
      "round_recruitment",
      "admission",
    ]);
    expect(result.current.stagesByUser.get(12)).toEqual(["midterm_reminder"]);
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

  it("reloads in place", async () => {
    listNotifiedStages.mockResolvedValueOnce([]);
    listNotifiedStages.mockResolvedValueOnce([
      { userId: 11, stages: ["admission"] },
    ]);
    const { result } = renderHook(() => useNotifiedStages("7"));
    await waitFor(() => expect(listNotifiedStages).toHaveBeenCalledTimes(1));

    await act(() => result.current.reload());
    expect(result.current.stagesByUser.get(11)).toEqual(["admission"]);
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
