import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useMentorshipData } from "@/pages/PersonalDashboard/hooks/useMentorshipData";
import {
  getAllMentorshipRounds,
  getMyMentorshipRegistration,
  getMyMentorshipPartners,
  postMyMentorshipRegistration,
  getMyMentorshipMatchResult,
  getMyMentorshipMeetingLog,
} from "@/api/mentorshipApi";
import {
  calculateMentorshipSlots,
  calculateRoundStatus,
} from "@/pages/PersonalDashboard/utils/mentorshipRounds";

vi.mock("@/api/mentorshipApi", () => ({
  getAllMentorshipRounds: vi.fn(),
  getMyMentorshipPartners: vi.fn(),
  getMyMentorshipRegistration: vi.fn(),
  postMyMentorshipRegistration: vi.fn(),
  getMyMentorshipMatchResult: vi.fn(),
  getMyMentorshipMeetingLog: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/utils/mentorshipRounds", () => ({
  calculateMentorshipSlots: vi.fn(),
  calculateRoundStatus: vi.fn(),
}));

describe("useMentorshipData Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    calculateRoundStatus.mockReturnValue({
      sortedRounds: [],
      activeRoundId: null,
    });
  });

  it("should fetch match results if the user is registered", async () => {
    // 1. Setup Rounds and Slots
    getAllMentorshipRounds.mockResolvedValue({ data: [{ id: "round-1" }] });
    calculateMentorshipSlots.mockReturnValue({
      regRoundId: "round-1",
      canViewMatch: true,
    });

    // 2. Setup Registration (User IS registered)
    const mockRegData = { id: "reg-123", isRegistered: true };
    getMyMentorshipRegistration.mockResolvedValue({ data: mockRegData });

    // 3. Setup Match Result
    const mockMatchData = {
      currentStatus: "matched",
      partners: [{ id: "p1" }],
    };
    getMyMentorshipMatchResult.mockResolvedValue({ data: mockMatchData });

    const { result } = renderHook(() => useMentorshipData());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Verify both APIs were called
    expect(getMyMentorshipRegistration).toHaveBeenCalledWith("round-1");
    expect(getMyMentorshipMatchResult).toHaveBeenCalledWith("round-1");

    // Verify state update
    expect(result.current.matchResult).toEqual(mockMatchData);
  });

  it("should NOT fetch match results if the user is not registered", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [{ id: "round-1" }] });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: "round-1" });

    // User is NOT registered
    const mockRegData = { id: "reg-123", isRegistered: false };
    getMyMentorshipRegistration.mockResolvedValue({ data: mockRegData });

    const { result } = renderHook(() => useMentorshipData());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(getMyMentorshipRegistration).toHaveBeenCalled();
    // Verify match result API was skipped
    expect(getMyMentorshipMatchResult).not.toHaveBeenCalled();
    expect(result.current.matchResult).toBeNull();
  });

  it("should handle match result API failure gracefully", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    getAllMentorshipRounds.mockResolvedValue({ data: [{ id: "round-1" }] });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: "round-1" });

    // Registration succeeds
    getMyMentorshipRegistration.mockResolvedValue({
      data: { isRegistered: true },
    });

    // Match result fails
    getMyMentorshipMatchResult.mockRejectedValue(new Error("Match API Error"));

    const { result } = renderHook(() => useMentorshipData());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Hook should still finish loading even if match fetch fails
    expect(result.current.isLoading).toBe(false);
    expect(result.current.matchResult).toBeNull();
    expect(consoleSpy).toHaveBeenCalledWith(
      "Failed to fetch match result",
      expect.any(Error),
    );

    consoleSpy.mockRestore();
  });

  it("should fetch rounds on initial load and fetch registration data based on the result", async () => {
    const mockRounds = [{ id: "round-1" }];
    getAllMentorshipRounds.mockResolvedValue({ data: mockRounds });

    const mockStatus = {
      regRoundId: "round-1",
      feedbackRoundId: null,
      isRegistrationOpen: true,
      isFeedbackEnabled: false,
    };
    calculateMentorshipSlots.mockReturnValue(mockStatus);

    const mockRegData = { id: "reg-123", status: "SUBMITTED" };
    getMyMentorshipRegistration.mockResolvedValue({ data: mockRegData });

    const { result } = renderHook(() => useMentorshipData());

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.regRoundId).toBe("round-1");
    expect(result.current.registration).toEqual(mockRegData);
    expect(getAllMentorshipRounds).toHaveBeenCalledTimes(1);
    expect(getMyMentorshipRegistration).toHaveBeenCalledWith("round-1");
  });

  it("should not call getMyMentorshipRegistration when regRoundId is null", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    calculateMentorshipSlots.mockReturnValue({
      regRoundId: null,
      isRegistrationOpen: false,
    });

    const { result } = renderHook(() => useMentorshipData());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(getMyMentorshipRegistration).not.toHaveBeenCalled();
    expect(result.current.registration).toBeNull();
  });

  it("should fetch partners when loadPastPartners is called", async () => {
    const mockPartners = [{ name: "Mentor A" }];
    getMyMentorshipPartners.mockResolvedValue({ data: mockPartners });
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    calculateMentorshipSlots.mockReturnValue({});

    const { result } = renderHook(() => useMentorshipData());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await act(async () => {
      await result.current.loadPastPartners();
    });

    expect(result.current.isPartnersLoading).toBe(false);
    expect(result.current.pastPartners).toEqual(mockPartners);
    expect(getMyMentorshipPartners).toHaveBeenCalledTimes(1);
  });

  it("should return early and not trigger API when saveRegistration is called while registration is closed", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    calculateMentorshipSlots.mockReturnValue({
      regRoundId: "round-1",
      isRegistrationOpen: false, // registration closed
    });

    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.saveRegistration({ some: "data" });
    });

    expect(postMyMentorshipRegistration).not.toHaveBeenCalled();
  });

  it("should call postMyMentorshipRegistration when saveRegistration is called while registration is open", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    calculateMentorshipSlots.mockReturnValue({
      regRoundId: "round-1",
      isRegistrationOpen: true,
    });
    postMyMentorshipRegistration.mockResolvedValue({ success: true });

    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const testData = { name: "New Reg" };
    await act(async () => {
      await result.current.saveRegistration(testData);
    });

    expect(postMyMentorshipRegistration).toHaveBeenCalledWith(
      "round-1",
      testData,
    );
  });

  it("should stop loading and log an error when the API request fails", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    getAllMentorshipRounds.mockRejectedValue(new Error("Network Error"));

    const { result } = renderHook(() => useMentorshipData());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it("should refresh registration data successfully when regRoundId exists", async () => {
    // Initialize data: simulate an active registration round
    const mockStatus = {
      regRoundId: "round-999",
      isRegistrationOpen: true,
    };
    getAllMentorshipRounds.mockResolvedValue({ data: [{ id: "round-999" }] });
    calculateMentorshipSlots.mockReturnValue(mockStatus);

    // Initial data retrieval
    getMyMentorshipRegistration.mockResolvedValueOnce({
      data: { id: "reg-1", status: "PENDING" },
    });

    const { result } = renderHook(() => useMentorshipData());

    // Wait for initialization to complete
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.registration?.status).toBe("PENDING");

    // Simulate data change during refresh
    const updatedRegData = { id: "reg-1", status: "SUBMITTED" };
    getMyMentorshipRegistration.mockResolvedValueOnce({ data: updatedRegData });

    // Trigger refresh action
    await act(async () => {
      await result.current.refreshRegistration();
    });

    expect(getMyMentorshipRegistration).toHaveBeenCalledTimes(2); // Initial call + refresh call
    expect(result.current.registration).toEqual(updatedRegData);
    expect(result.current.registration.status).toBe("SUBMITTED");
  });

  it("should not call API if regRoundId is missing during refresh", async () => {
    // Simulate scenario where there is no active round
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: null });

    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // Reset mock call count to ensure no interference from initialization
    getMyMentorshipRegistration.mockClear();

    // Trigger refresh
    await act(async () => {
      await result.current.refreshRegistration();
    });

    // Assert that the API was not called
    expect(getMyMentorshipRegistration).not.toHaveBeenCalled();
  });

  it("should log an error when refreshRegistration API fails", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    // Simulate environment: with a round ID
    getAllMentorshipRounds.mockResolvedValue({ data: [{ id: "round-1" }] });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: "round-1" });
    getMyMentorshipRegistration.mockResolvedValueOnce({ data: {} }); // Initial load success

    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // Simulate refresh failure
    getMyMentorshipRegistration.mockRejectedValueOnce(
      new Error("Refresh Failed"),
    );

    await act(async () => {
      await result.current.refreshRegistration();
    });

    // Assert that the error was captured
    expect(consoleSpy).toHaveBeenCalledWith(
      "Failed to refresh registration",
      expect.any(Error),
    );

    consoleSpy.mockRestore();
  });
});

describe("refreshMeetings", () => {
  const mockRound = { id: "round-1", name: "Spring 2026", requiredMeetings: 5 };

  beforeEach(() => {
    vi.clearAllMocks();
    getAllMentorshipRounds.mockResolvedValue({ data: [mockRound] });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: null });
    calculateRoundStatus.mockReturnValue({
      sortedRounds: [mockRound],
      activeRoundId: "round-1",
    });
  });

  it("should build partnerMeetingOverview with merged meeting data", async () => {
    getMyMentorshipMeetingLog.mockResolvedValue({
      data: {
        userTimezone: "Asia/Shanghai",
        meetingInfo: [
          {
            partnerId: 99,
            participantRole: "Mentee",
            meetingTimeList: [
              {
                meetingId: "m1",
                startDatetime: "2026-03-18T02:00:00Z",
                endDatetime: "2026-03-18T03:00:00Z",
                isCompleted: true,
              },
            ],
          },
        ],
      },
    });
    getMyMentorshipPartners.mockResolvedValue({
      data: [{ id: 99, preferredName: "Alice" }],
    });

    const { result } = renderHook(() => useMentorshipData());

    await waitFor(() => {
      expect(result.current.participantDetails.roundInfo).not.toBeNull();
    });

    const overview = result.current.participantDetails.partnerMeetingOverview;
    expect(overview).toHaveLength(1);
    expect(overview[0]).toEqual(
      expect.objectContaining({
        partnerId: 99,
        preferredName: "Alice",
        requiredMeetings: 5,
        completedCount: 1,
        completedRate: 20,
      }),
    );
    expect(getMyMentorshipMeetingLog).toHaveBeenCalledWith("round-1");
    expect(getMyMentorshipPartners).toHaveBeenCalledWith("round-1");
  });

  it("should set empty partnerMeetingOverview when no partners are found", async () => {
    getMyMentorshipMeetingLog.mockResolvedValue({ data: { meetingInfo: [] } });
    getMyMentorshipPartners.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useMentorshipData());

    await waitFor(() =>
      expect(result.current.participantDetails.roundInfo).not.toBeNull(),
    );

    expect(result.current.participantDetails.partnerMeetingOverview).toEqual(
      [],
    );
  });

  it("should set completedRate to 0 when there are no completed meetings", async () => {
    getMyMentorshipMeetingLog.mockResolvedValue({
      data: {
        userTimezone: "America/New_York",
        meetingInfo: [
          {
            partnerId: 5,
            participantRole: "Mentee",
            meetingTimeList: [],
          },
        ],
      },
    });
    getMyMentorshipPartners.mockResolvedValue({
      data: [{ id: 5, preferredName: "Bob" }],
    });

    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() =>
      expect(
        result.current.participantDetails.partnerMeetingOverview,
      ).toHaveLength(1),
    );

    const overview = result.current.participantDetails.partnerMeetingOverview;
    expect(overview[0].completedCount).toBe(0);
    expect(overview[0].completedRate).toBe(0);
  });

  it("should set userTimezone from meeting log response", async () => {
    getMyMentorshipMeetingLog.mockResolvedValue({
      data: { userTimezone: "America/New_York", meetingInfo: [] },
    });
    getMyMentorshipPartners.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useMentorshipData());

    await waitFor(() =>
      expect(result.current.participantDetails.roundInfo).not.toBeNull(),
    );

    expect(result.current.userTimezone).toBe("America/New_York");
  });

  it("should not call getMyMentorshipPartners again when switching back to a cached round", async () => {
    getMyMentorshipMeetingLog.mockResolvedValue({ data: { meetingInfo: [] } });
    getMyMentorshipPartners.mockResolvedValue({
      data: [{ id: 1, preferredName: "Alice" }],
    });

    const switchAndWait = async (roundId) => {
      act(() => result.current.handleRoundChange(roundId));
      await waitFor(() => {
        expect(result.current.selectedRoundId).toBe(roundId);
        expect(result.current.isMeetingsLoading).toBe(false);
      });
    };

    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    await switchAndWait("round-2");
    await switchAndWait("round-1");

    const round1Calls = getMyMentorshipPartners.mock.calls.filter(
      (c) => c[0] === "round-1",
    );
    expect(round1Calls).toHaveLength(1);
  });

  it("should log an error and stop loading when the API call fails", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    getMyMentorshipMeetingLog.mockRejectedValue(new Error("API Error"));
    getMyMentorshipPartners.mockRejectedValue(new Error("API Error"));

    renderHook(() => useMentorshipData());

    await waitFor(() =>
      expect(consoleSpy).toHaveBeenCalledWith(
        "Failed to fetch meeting log",
        expect.any(Error),
      ),
    );

    expect(consoleSpy).toHaveBeenCalledWith(
      "Failed to fetch meeting log",
      expect.any(Error),
    );
    consoleSpy.mockRestore();
  });
});

describe("handleRoundChange", () => {
  const mockRound = { id: "round-1", requiredMeetings: 3 };

  beforeEach(() => {
    vi.clearAllMocks();
    getAllMentorshipRounds.mockResolvedValue({ data: [mockRound] });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: null });
    calculateRoundStatus.mockReturnValue({
      sortedRounds: [mockRound],
      activeRoundId: "round-1",
    });
    getMyMentorshipMeetingLog.mockResolvedValue({ data: { meetingInfo: [] } });
    getMyMentorshipPartners.mockResolvedValue({ data: [] });
  });

  it("should update selectedRoundId when a different round is selected", async () => {
    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() =>
      expect(result.current.participantDetails.roundInfo).not.toBeNull(),
    );

    act(() => {
      result.current.handleRoundChange("round-2");
    });

    expect(result.current.selectedRoundId).toBe("round-2");
  });

  it("should clear participantDetails immediately when switching to a different round", async () => {
    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() =>
      expect(result.current.participantDetails.roundInfo).not.toBeNull(),
    );

    act(() => {
      result.current.handleRoundChange("round-2");
    });

    // Stale data should be cleared right away before the new round loads
    expect(result.current.participantDetails.partnerMeetingOverview).toEqual(
      [],
    );
    expect(result.current.participantDetails.participantRole).toBeNull();
  });

  it("should not clear participantDetails when the same round is re-selected", async () => {
    getMyMentorshipPartners.mockResolvedValue({
      data: [{ id: 1, preferredName: "Alice" }],
    });

    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() =>
      expect(
        result.current.participantDetails.partnerMeetingOverview,
      ).toHaveLength(1),
    );

    const detailsBefore = result.current.participantDetails;

    act(() => {
      result.current.handleRoundChange("round-1");
    });

    expect(result.current.participantDetails).toEqual(detailsBefore);
  });
});
