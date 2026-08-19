import React from "react";
import { renderHook, waitFor, act } from "@testing-library/react";
import { FlagsProvider } from "@/context/flags";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useMentorshipData } from "@/pages/PersonalDashboard/hooks/useMentorshipData";
import {
  getAllMentorshipRounds,
  getMyMentorshipRegistration,
  getMyMentorshipPartners,
  postMyMentorshipRegistration,
  getMyMentorshipMatchResult,
  getMyMentorshipMeetingLog,
} from "@/api/mentorshipApi";
import { getMyMentorshipMeetingsV2 } from "@/api/meetingApi";
import {
  calculateMentorshipSlots,
  calculateRoundStatus,
} from "@/pages/PersonalDashboard/utils/mentorshipRounds";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";

vi.mock("@/api/mentorshipApi", () => ({
  getAllMentorshipRounds: vi.fn(),
  getMyMentorshipPartners: vi.fn(),
  getMyMentorshipRegistration: vi.fn(),
  postMyMentorshipRegistration: vi.fn(),
  getMyMentorshipMatchResult: vi.fn(),
  getMyMentorshipMeetingLog: vi.fn(),
}));
vi.mock("@/api/meetingApi", () => ({
  getMyMentorshipMeetingsV2: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/utils/mentorshipRounds", () => ({
  calculateMentorshipSlots: vi.fn(),
  calculateRoundStatus: vi.fn(),
}));

vi.mock("@/hooks/useFeatureFlags", () => ({
  useFeatureFlags: vi.fn(),
}));

describe("useMentorshipData Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ "create-google-meeting": false });
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

  it("does not fetch mentorship rounds when enabled is false", () => {
    const { result } = renderHook(() => useMentorshipData({ enabled: false }));
    expect(getAllMentorshipRounds).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });

  it("still fetches mentorship rounds when enabled is true", () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    renderHook(() => useMentorshipData({ enabled: true }));
    expect(getAllMentorshipRounds).toHaveBeenCalledTimes(1);
  });

  it("defaults to fetching when enabled is omitted (backward compatible)", () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    renderHook(() => useMentorshipData());
    expect(getAllMentorshipRounds).toHaveBeenCalledTimes(1);
  });

  it("goes back to loading when it is enabled after being disabled", () => {
    // The disabled pass resolves isLoading to false. Without re-raising
    // it, callers who wait on isLoading read the empty initial state --
    // no open round, no deadline -- as a finished answer.
    getAllMentorshipRounds.mockReturnValue(new Promise(() => {}));

    const { result, rerender } = renderHook(
      ({ enabled }) => useMentorshipData({ enabled }),
      { initialProps: { enabled: false } },
    );
    expect(result.current.isLoading).toBe(false);

    rerender({ enabled: true });

    expect(result.current.isLoading).toBe(true);
  });
});

describe("saveRegistration", () => {
  const MOCK_TODAY = "2026-01-15T00:00:00Z";

  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ "create-google-meeting": false });
    calculateRoundStatus.mockReturnValue({
      sortedRounds: [],
      activeRoundId: null,
    });
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(MOCK_TODAY));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should return early and not trigger API when saveRegistration is called while registration is closed", async () => {
    getAllMentorshipRounds.mockResolvedValue({
      data: [
        {
          id: "round-1",
          timeline: {
            mentorApplicationDeadlineAt: "2026-01-01T00:00:00Z", // before MOCK_TODAY
            menteeApplicationDeadlineAt: "2026-01-01T00:00:00Z", // before MOCK_TODAY
          },
        },
      ],
    });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: "round-1" });
    getMyMentorshipRegistration.mockResolvedValue({
      data: { isRegistered: false, roundPreferences: null },
    });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.saveRegistration({
        roundPreferences: { participantRole: "mentee" },
      });
    });

    expect(postMyMentorshipRegistration).not.toHaveBeenCalled();
  });

  it("should call postMyMentorshipRegistration when saveRegistration is called while registration is open", async () => {
    getAllMentorshipRounds.mockResolvedValue({
      data: [
        {
          id: "round-1",
          timeline: {
            mentorApplicationDeadlineAt: "2026-02-01T00:00:00Z", // after MOCK_TODAY
            menteeApplicationDeadlineAt: "2026-02-01T00:00:00Z", // after MOCK_TODAY
          },
        },
      ],
    });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: "round-1" });
    getMyMentorshipRegistration.mockResolvedValue({
      data: { isRegistered: false, roundPreferences: null },
    });
    postMyMentorshipRegistration.mockResolvedValue({ success: true });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const testData = { roundPreferences: { participantRole: "mentee" } };
    await act(async () => {
      await result.current.saveRegistration(testData);
    });

    expect(postMyMentorshipRegistration).toHaveBeenCalledWith(
      "round-1",
      testData,
    );
  });

  // Each role has its own window, so a save is gated on the window of the
  // role the payload actually names -- not on whether anything is open.
  it("refuses a save for a role whose own window has closed", async () => {
    getAllMentorshipRounds.mockResolvedValue({
      data: [
        {
          id: "round-1",
          timeline: {
            mentorApplicationDeadlineAt: "2026-01-01T00:00:00Z", // closed
            menteeApplicationDeadlineAt: "2026-02-01T00:00:00Z", // open
          },
        },
      ],
    });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: "round-1" });
    getMyMentorshipRegistration.mockResolvedValue({
      data: { isRegistered: false, roundPreferences: null },
    });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor", "mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.saveRegistration({
        roundPreferences: { participantRole: "mentor" },
      });
    });

    expect(postMyMentorshipRegistration).not.toHaveBeenCalled();
  });

  it("refuses a save whose payload names no role at all", async () => {
    getAllMentorshipRounds.mockResolvedValue({
      data: [
        {
          id: "round-1",
          timeline: {
            mentorApplicationDeadlineAt: "2026-02-01T00:00:00Z",
            menteeApplicationDeadlineAt: "2026-02-01T00:00:00Z",
          },
        },
      ],
    });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: "round-1" });
    getMyMentorshipRegistration.mockResolvedValue({
      data: { isRegistered: false, roundPreferences: null },
    });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.saveRegistration({ roundPreferences: {} });
    });

    expect(postMyMentorshipRegistration).not.toHaveBeenCalled();
  });
});

describe("registration entries by role", () => {
  const MOCK_TODAY = "2026-01-15T00:00:00Z";
  const PAST = "2026-01-01T00:00:00Z";
  const FUTURE = "2026-02-01T00:00:00Z";
  const LATER = "2026-03-01T00:00:00Z";

  /**
   * A round whose two role deadlines disagree, so the assertion can only
   * pass if the hook read the right one for each role.
   */
  const mockRoundWith = ({ mentor, mentee }) => {
    getAllMentorshipRounds.mockResolvedValue({
      data: [
        {
          id: "round-1",
          name: "2026 Fall",
          timeline: {
            mentorApplicationDeadlineAt: mentor,
            menteeApplicationDeadlineAt: mentee,
          },
        },
      ],
    });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: "round-1" });
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ "create-google-meeting": false });
    calculateRoundStatus.mockReturnValue({
      sortedRounds: [],
      activeRoundId: null,
    });
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(MOCK_TODAY));
    // A first-time registrant: registered for nothing, and the role-less
    // read carries no round preferences to settle a role from.
    getMyMentorshipRegistration.mockResolvedValue({
      data: { isRegistered: false, roundPreferences: null },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("offers one entry per eligible role, each gated on its own deadline", async () => {
    mockRoundWith({ mentor: FUTURE, mentee: PAST });

    const { result } = renderHook(() =>
      useMentorshipData({
        enabled: true,
        hiredMentorshipRoles: ["mentor", "mentee"],
      }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.registrationEntries).toEqual([
      { role: "mentor", deadlineAt: FUTURE, isOpen: true },
      { role: "mentee", deadlineAt: PAST, isOpen: false },
    ]);
    expect(result.current.registeredRole).toBeNull();
  });

  it("offers a single entry to a single-admission participant", async () => {
    mockRoundWith({ mentor: PAST, mentee: FUTURE });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.registrationEntries).toEqual([
      { role: "mentee", deadlineAt: FUTURE, isOpen: true },
    ]);
  });

  it("offers nothing to someone holding no admission", async () => {
    mockRoundWith({ mentor: FUTURE, mentee: FUTURE });

    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.registrationEntries).toEqual([]);
    expect(result.current.isRegistrationOpen).toBe(false);
  });

  it("collapses to the registered role once the user has registered", async () => {
    mockRoundWith({ mentor: FUTURE, mentee: FUTURE });
    getMyMentorshipRegistration.mockResolvedValue({
      data: {
        isRegistered: true,
        roundPreferences: { participantRole: "mentee", goal: "g" },
      },
    });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor", "mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.registeredRole).toBe("mentee");
    expect(result.current.registrationEntries.map((e) => e.role)).toEqual([
      "mentee",
    ]);
  });

  // A settled role stays reachable read-only after its window shuts.
  it("keeps the registered role's entry after its deadline has passed", async () => {
    mockRoundWith({ mentor: FUTURE, mentee: PAST });
    getMyMentorshipRegistration.mockResolvedValue({
      data: {
        isRegistered: true,
        roundPreferences: { participantRole: "mentee" },
      },
    });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor", "mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.registrationEntries).toEqual([
      { role: "mentee", deadlineAt: PAST, isOpen: false },
    ]);
    expect(result.current.isRegistrationOpen).toBe(false);
  });

  it("asks about the round without naming a role", async () => {
    mockRoundWith({ mentor: FUTURE, mentee: FUTURE });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor", "mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(getMyMentorshipRegistration).toHaveBeenCalledWith("round-1");
  });

  it("measures a first-time mentor against the mentor deadline", async () => {
    mockRoundWith({ mentor: FUTURE, mentee: PAST });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.isRegistrationOpen).toBe(true);
  });

  it("measures a first-time mentee against the mentee deadline", async () => {
    mockRoundWith({ mentor: PAST, mentee: FUTURE });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.isRegistrationOpen).toBe(true);
  });

  it("closes registration for a mentor once the mentor deadline has passed", async () => {
    mockRoundWith({ mentor: PAST, mentee: FUTURE });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.isRegistrationOpen).toBe(false);
  });

  it("exposes the deadline and round name the reminder names", async () => {
    mockRoundWith({ mentor: FUTURE, mentee: PAST });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.registrationDeadlineAt).toBe(FUTURE);
    expect(result.current.regRoundName).toBe("2026 Fall");
  });

  // The reminder names one date, so with two windows still open it names
  // the one that runs out first.
  it("names the earliest still-open window when both roles are open", async () => {
    mockRoundWith({ mentor: LATER, mentee: FUTURE });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor", "mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.isRegistrationOpen).toBe(true);
    expect(result.current.registrationDeadlineAt).toBe(FUTURE);
  });

  it("reports no deadline when no round is in a registration slot", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: null });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.registrationDeadlineAt).toBeNull();
    expect(result.current.isRegistrationOpen).toBe(false);
    expect(result.current.registrationEntries).toEqual([]);
  });

  it("fetches one role's prefill on demand", async () => {
    mockRoundWith({ mentor: FUTURE, mentee: FUTURE });
    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor", "mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const prefill = { isRegistered: false, roundPreferences: { maxPartners: 2 } };
    getMyMentorshipRegistration.mockResolvedValueOnce({ data: prefill });

    let loaded;
    await act(async () => {
      loaded = await result.current.loadRegistrationForRole("mentor");
    });

    expect(getMyMentorshipRegistration).toHaveBeenLastCalledWith(
      "round-1",
      "mentor",
    );
    expect(loaded).toEqual(prefill);
  });

  it("returns nothing from loadRegistrationForRole when no round takes registrations", async () => {
    getAllMentorshipRounds.mockResolvedValue({ data: [] });
    calculateMentorshipSlots.mockReturnValue({ regRoundId: null });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    getMyMentorshipRegistration.mockClear();

    let loaded;
    await act(async () => {
      loaded = await result.current.loadRegistrationForRole("mentor");
    });

    expect(loaded).toBeNull();
    expect(getMyMentorshipRegistration).not.toHaveBeenCalled();
  });

  // Refreshing after a save settles the round's role, so the other role's
  // entry must stop being offered without waiting for a full reload.
  it("collapses the entries when a refresh reports a new registration", async () => {
    mockRoundWith({ mentor: FUTURE, mentee: FUTURE });

    const { result } = renderHook(() =>
      useMentorshipData({ hiredMentorshipRoles: ["mentor", "mentee"] }),
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.registrationEntries).toHaveLength(2);

    getMyMentorshipRegistration.mockResolvedValueOnce({
      data: {
        isRegistered: true,
        roundPreferences: { participantRole: "mentor" },
      },
    });
    await act(async () => {
      await result.current.refreshRegistration();
    });

    expect(result.current.registeredRole).toBe("mentor");
    expect(result.current.registrationEntries.map((e) => e.role)).toEqual([
      "mentor",
    ]);
  });
});

describe("refreshMeetings", () => {
  const mockRound = { id: "round-1", name: "Spring 2026", requiredMeetings: 5 };

  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ "create-google-meeting": false });
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
            completedMeetingsCount: 1,
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
            completedMeetingsCount: 0,
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
        expect(result.current.isParticipantCardLoading).toBe(false);
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

  it("should call V2 API when create-google-meeting flag is on", async () => {
    useFeatureFlags.mockReturnValue({ "create-google-meeting": true });
    getMyMentorshipMeetingsV2.mockResolvedValue({ data: { meetingInfo: [] } });
    getMyMentorshipPartners.mockResolvedValue({ data: [] });

    const { result } = renderHook(() => useMentorshipData());

    await waitFor(() =>
      expect(result.current.participantDetails.roundInfo).not.toBeNull(),
    );

    expect(getMyMentorshipMeetingsV2).toHaveBeenCalledTimes(1);
    expect(getMyMentorshipMeetingsV2).toHaveBeenCalledWith({
      roundId: "round-1",
      includeDetails: false,
    });
    expect(getMyMentorshipMeetingLog).not.toHaveBeenCalled();
  });

  it("ignores a stale round's late response after switching rounds", async () => {
    const round1 = { id: "round-1", name: "R1", requiredMeetings: 5 };
    const round2 = { id: "round-2", name: "R2", requiredMeetings: 5 };
    calculateRoundStatus.mockReturnValue({
      sortedRounds: [round1, round2],
      activeRoundId: "round-1",
    });
    getAllMentorshipRounds.mockResolvedValue({ data: [round1, round2] });
    getMyMentorshipMeetingLog.mockResolvedValue({ data: { meetingInfo: [] } });

    // Control partner resolution per round so round-1 (the round we leave)
    // resolves AFTER round-2 (the round we switch to).
    const resolvers = {};
    getMyMentorshipPartners.mockImplementation((roundId) => {
      return new Promise((resolve) => {
        resolvers[roundId] = resolve;
      });
    });

    const { result } = renderHook(() => useMentorshipData());
    await waitFor(() => expect(resolvers["round-1"]).toBeDefined());

    // Switch to round-2 before round-1's partners come back.
    act(() => result.current.handleRoundChange("round-2"));
    await waitFor(() => expect(resolvers["round-2"]).toBeDefined());

    // Newer round (round-2) resolves first and renders.
    await act(async () => {
      resolvers["round-2"]({ data: [{ id: 2, preferredName: "Bob" }] });
    });
    // Stale round (round-1) resolves last — it must NOT overwrite round-2.
    await act(async () => {
      resolvers["round-1"]({ data: [{ id: 1, preferredName: "Alice" }] });
    });

    const overview = result.current.participantDetails.partnerMeetingOverview;
    expect(overview).toHaveLength(1);
    expect(overview[0].preferredName).toBe("Bob");
  });

  it("clears loading state after a StrictMode remount", async () => {
    const round1 = { id: "round-1", name: "R1", requiredMeetings: 5 };
    calculateRoundStatus.mockReturnValue({
      sortedRounds: [round1],
      activeRoundId: "round-1",
    });
    getAllMentorshipRounds.mockResolvedValue({ data: [round1] });
    getMyMentorshipMeetingLog.mockResolvedValue({ data: { meetingInfo: [] } });
    getMyMentorshipPartners.mockResolvedValue({
      data: [{ id: 1, preferredName: "Alice" }],
    });

    const { result } = renderHook(() => useMentorshipData(), {
      wrapper: ({ children }) =>
        React.createElement(React.StrictMode, null, children),
    });

    await waitFor(() =>
      expect(result.current.isParticipantCardLoading).toBe(false),
    );
  });
});

describe("handleRoundChange", () => {
  const mockRound = { id: "round-1", requiredMeetings: 3 };

  beforeEach(() => {
    vi.clearAllMocks();
    useFeatureFlags.mockReturnValue({ "create-google-meeting": false });
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
