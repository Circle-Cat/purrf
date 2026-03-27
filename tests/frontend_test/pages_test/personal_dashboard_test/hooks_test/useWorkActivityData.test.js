import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useWorkActivityData } from "@/pages/PersonalDashboard/hooks/useWorkActivityData";
import { getMySummary } from "@/api/dashboardApi";

vi.mock("@/api/dashboardApi", () => ({
  getMySummary: vi.fn(),
}));

describe("useWorkActivityData Hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should NOT fetch data when enabled is false", async () => {
    renderHook(() => useWorkActivityData({ enabled: false }));

    expect(getMySummary).not.toHaveBeenCalled();
  });

  it("should fetch data on mount when enabled is true", async () => {
    const mockData = {
      data: {
        jiraIssueDone: 5,
        clMerged: 3,
        locMerged: 100,
        meetingHours: 2,
        chatCount: 10,
      },
    };

    getMySummary.mockResolvedValue(mockData);

    const { result } = renderHook(() => useWorkActivityData());

    await waitFor(() => {
      expect(result.current.isPersonalSummaryLoading).toBe(false);
    });

    expect(getMySummary).toHaveBeenCalledTimes(1);

    expect(result.current.summary.summary).toEqual({
      jiraTickets: 5,
      mergedCLs: 3,
      mergedLOC: 100,
      meetingHours: 2,
      chatMessages: 10,
    });
  });

  it("should set loading state correctly during fetch", async () => {
    let resolveFn;
    const promise = new Promise((res) => {
      resolveFn = res;
    });

    getMySummary.mockReturnValue(promise);

    const { result } = renderHook(() => useWorkActivityData());

    // loading should be true initially
    expect(result.current.isPersonalSummaryLoading).toBe(true);

    act(() => {
      resolveFn({
        data: {
          jiraIssueDone: 1,
          clMerged: 1,
          locMerged: 1,
          meetingHours: 1,
          chatCount: 1,
        },
      });
    });

    await waitFor(() => {
      expect(result.current.isPersonalSummaryLoading).toBe(false);
    });
  });

  it("should handle API failure gracefully", async () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    getMySummary.mockRejectedValue(new Error("API Error"));

    const { result } = renderHook(() => useWorkActivityData());

    await waitFor(() => {
      expect(result.current.isPersonalSummaryLoading).toBe(false);
    });

    expect(consoleSpy).toHaveBeenCalledWith(
      "Failed to fetch summary",
      expect.any(Error),
    );

    consoleSpy.mockRestore();
  });

  it("should allow manual fetch via fetchPersonalSummary", async () => {
    const mockData = {
      data: {
        jiraIssueDone: 2,
        clMerged: 2,
        locMerged: 200,
        meetingHours: 4,
        chatCount: 20,
      },
    };

    getMySummary.mockResolvedValue(mockData);

    const { result } = renderHook(() =>
      useWorkActivityData({ enabled: false }),
    );

    await act(async () => {
      await result.current.fetchPersonalSummary("2024-01-01", "2024-01-31");
    });

    expect(getMySummary).toHaveBeenCalledWith({
      startDate: "2024-01-01",
      endDate: "2024-01-31",
    });

    expect(result.current.summary.summary).toEqual({
      jiraTickets: 2,
      mergedCLs: 2,
      mergedLOC: 200,
      meetingHours: 4,
      chatMessages: 20,
    });
  });

  it("should fallback to 0 when API returns undefined fields", async () => {
    getMySummary.mockResolvedValue({
      data: {},
    });

    const { result } = renderHook(() => useWorkActivityData());

    await waitFor(() => {
      expect(result.current.isPersonalSummaryLoading).toBe(false);
    });

    expect(result.current.summary.summary).toEqual({
      jiraTickets: 0,
      mergedCLs: 0,
      mergedLOC: 0,
      meetingHours: 0,
      chatMessages: 0,
    });
  });
});
