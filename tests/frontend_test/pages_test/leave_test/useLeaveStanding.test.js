import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";

import { useLeaveStanding } from "@/pages/Leave/hooks/useLeaveStanding";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

const envelope = (isCovered) => ({
  success: true,
  message: "ok",
  data: { isCovered },
});

describe("useLeaveStanding", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not claim coverage while loading", () => {
    api.getLeaveCoverage.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useLeaveStanding());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.isCovered).toBe(false);
  });

  it("does not claim coverage after a failed load", async () => {
    // Fails closed: offering a screen we could not confirm is worse than
    // making somebody covered wait a moment.
    api.getLeaveCoverage.mockRejectedValue(new Error("network error"));

    const { result } = renderHook(() => useLeaveStanding());

    await waitFor(() => expect(result.current.loadError).toBe(true));
    expect(result.current.isCovered).toBe(false);
  });

  it("reports coverage the server confirms", async () => {
    api.getLeaveCoverage.mockResolvedValue(envelope(true));

    const { result } = renderHook(() => useLeaveStanding());

    await waitFor(() => expect(result.current.isCovered).toBe(true));
  });

  it("reports no coverage when the server says so", async () => {
    api.getLeaveCoverage.mockResolvedValue(envelope(false));

    const { result } = renderHook(() => useLeaveStanding());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isCovered).toBe(false);
  });

  it("keeps the figures on screen while it refreshes them", async () => {
    // Refreshed after filing. Dropping to "loading" would take the card,
    // dialog and all, off the dashboard for the length of the request.
    api.getLeaveCoverage.mockResolvedValue({
      data: { isCovered: true, availableHours: "56.00", pendingHours: "0.00" },
    });
    const { result } = renderHook(() => useLeaveStanding());
    await waitFor(() => expect(result.current.isCovered).toBe(true));

    let finish;
    api.getLeaveCoverage.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    act(() => {
      result.current.refresh();
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.isCovered).toBe(true);
    expect(result.current.availableHours).toBe("56.00");

    await act(async () => {
      finish({
        data: {
          isCovered: true,
          availableHours: "32.00",
          pendingHours: "24.00",
        },
      });
    });

    expect(result.current.availableHours).toBe("32.00");
    expect(result.current.pendingHours).toBe("24.00");
  });

  it("keeps the figures it has when a refresh fails", async () => {
    api.getLeaveCoverage.mockResolvedValue({
      data: { isCovered: true, availableHours: "56.00" },
    });
    const { result } = renderHook(() => useLeaveStanding());
    await waitFor(() => expect(result.current.isCovered).toBe(true));

    api.getLeaveCoverage.mockRejectedValue(new Error("network error"));
    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.loadError).toBe(false);
    expect(result.current.availableHours).toBe("56.00");
  });

  it("asks nothing while the feature is switched off", () => {
    const { result } = renderHook(() => useLeaveStanding({ enabled: false }));

    expect(api.getLeaveCoverage).not.toHaveBeenCalled();
    expect(result.current.isCovered).toBe(false);
  });
});
