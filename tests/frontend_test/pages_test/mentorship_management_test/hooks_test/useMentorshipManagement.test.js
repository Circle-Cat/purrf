import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useMentorshipManagement } from "@/pages/MentorshipManagement/hooks/useMentorshipManagement";
import {
  getAllMentorshipRounds,
  upsertMentorshipRound,
} from "@/api/mentorshipApi";
import { calculateRoundStatus } from "@/pages/PersonalDashboard/utils/mentorshipRounds";

vi.mock("@/api/mentorshipApi", () => ({
  getAllMentorshipRounds: vi.fn(),
  upsertMentorshipRound: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/utils/mentorshipRounds", () => ({
  calculateRoundStatus: vi.fn(),
}));

const makeTestRound = (overrides = {}) => ({
  id: 1,
  name: "Mentorship 2026 Spring",
  activePairs: 26,
  matchedParticipants: 52,
  totalCompletedMeetings: 93,
  menteeAverageScore: 4.8,
  mentorAverageScore: null,
  requiredMeetings: 5,
  status: "active",
  ...overrides,
});

describe("useMentorshipManagement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    calculateRoundStatus.mockReturnValue({ sortedRounds: [] });
  });

  it("fetches rounds with needDetails=true and resolves loading", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useMentorshipManagement());

    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(getAllMentorshipRounds).toHaveBeenCalledWith(true);
  });

  it("skips the fetch and stops loading when canReadRounds is false", async () => {
    const { result } = renderHook(() => useMentorshipManagement(false));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(getAllMentorshipRounds).not.toHaveBeenCalled();
    expect(result.current.sortedRounds).toEqual([]);
  });

  it("passes rounds through calculateRoundStatus and computes totals correctly", async () => {
    const rounds = [
      makeTestRound({
        id: 1,
        matchedParticipants: 52,
        totalCompletedMeetings: 93,
      }),
      makeTestRound({
        id: 2,
        matchedParticipants: 50,
        totalCompletedMeetings: 99,
      }),
    ];
    getAllMentorshipRounds.mockResolvedValue({ data: rounds });
    calculateRoundStatus.mockReturnValue({
      sortedRounds: [
        makeTestRound({ id: 1, status: "completed" }),
        makeTestRound({ id: 2, status: "completed" }),
        makeTestRound({ id: 3, status: "active" }),
      ],
    });

    const { result } = renderHook(() => useMentorshipManagement());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(calculateRoundStatus).toHaveBeenCalledWith(rounds);
    expect(result.current.totals.totalCompletedRounds).toBe(2);
    expect(result.current.totals.totalParticipants).toBe(102);
    expect(result.current.totals.totalMeetings).toBe(192);
  });

  it("treats null matchedParticipants and totalCompletedMeetings as 0 in totals", async () => {
    const rounds = [
      makeTestRound({
        matchedParticipants: null,
        totalCompletedMeetings: null,
      }),
    ];
    getAllMentorshipRounds.mockResolvedValue({ data: rounds });
    calculateRoundStatus.mockReturnValue({ sortedRounds: rounds });

    const { result } = renderHook(() => useMentorshipManagement());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.totals.totalParticipants).toBe(0);
    expect(result.current.totals.totalMeetings).toBe(0);
  });

  it("logs error and stops loading when fetch fails", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    getAllMentorshipRounds.mockRejectedValue(new Error("Network Error"));

    const { result } = renderHook(() => useMentorshipManagement());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(consoleSpy).toHaveBeenCalledWith(
      "Failed to fetch mentorship rounds",
      expect.any(Error),
    );
    consoleSpy.mockRestore();
  });

  it("saveRound calls upsertMentorshipRound, refreshes rounds, and closes modal", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    upsertMentorshipRound.mockResolvedValue({});

    const { result } = renderHook(() => useMentorshipManagement());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => result.current.openCreate());
    expect(result.current.roundModalState.open).toBe(true);

    const payload = { name: "Mentorship 2026 Spring", required_meetings: 5 };
    await act(async () => {
      await result.current.saveRound(payload);
    });

    expect(upsertMentorshipRound).toHaveBeenCalledWith(payload);
    expect(getAllMentorshipRounds).toHaveBeenCalledTimes(2);
    expect(result.current.roundModalState.open).toBe(false);
  });

  it("initialises closed, openCreate/openEdit/closeModal work correctly", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    const round = makeTestRound();
    const { result } = renderHook(() => useMentorshipManagement());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.roundModalState).toEqual({
      open: false,
      round: null,
    });

    act(() => result.current.openCreate());
    expect(result.current.roundModalState).toEqual({ open: true, round: null });

    act(() => result.current.openEdit(round));
    expect(result.current.roundModalState).toEqual({ open: true, round });

    act(() => result.current.closeModal());
    expect(result.current.roundModalState).toEqual({
      open: false,
      round: null,
    });
  });
});
