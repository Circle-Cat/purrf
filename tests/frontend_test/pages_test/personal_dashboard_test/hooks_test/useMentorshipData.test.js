import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useMentorshipData } from "@/pages/PersonalDashboard/hooks/useMentorshipData";
import {
  getAllMentorshipRounds,
  getMyMentorshipRegistration,
  getMyMentorshipPartners,
  postMyMentorshipRegistration,
  getMyMentorshipMatchResult,
} from "@/api/mentorshipApi";
import { calculateMentorshipSlots } from "@/pages/PersonalDashboard/utils/mentorshipRounds";

vi.mock("@/api/mentorshipApi", () => ({
  getAllMentorshipRounds: vi.fn(),
  getMyMentorshipPartners: vi.fn(),
  getMyMentorshipRegistration: vi.fn(),
  postMyMentorshipRegistration: vi.fn(),
  getMyMentorshipMatchResult: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/utils/mentorshipRounds", () => ({
  calculateMentorshipSlots: vi.fn(),
}));

describe("useMentorshipData Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
