import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getLeaveLedger } from "@/api/leaveApi";
import { useLeaveLedger } from "@/pages/Leave/hooks/useLeaveLedger";

vi.mock("@/api/leaveApi", () => ({
  getLeaveLedger: vi.fn(),
}));

describe("useLeaveLedger", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches and sets ledger data successfully on mount", async () => {
    const mockResponse = {
      data: {
        entries: [
          { entryId: 1, hours: "40.00", entryType: "weekly_accrual" },
          { entryId: 2, hours: "-8.00", entryType: "leave_deduction" },
        ],
        totalEntries: 2,
      },
    };
    getLeaveLedger.mockResolvedValueOnce(mockResponse);

    const { result } = renderHook(() => useLeaveLedger());

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(getLeaveLedger).toHaveBeenCalledWith({
      userId: null,
      page: 1,
      pageSize: 50,
    });
    expect(result.current.entries).toEqual(mockResponse.data.entries);
    expect(result.current.totalEntries).toBe(2);
    expect(result.current.loadError).toBe(false);
  });

  it("handles loading state and fetch errors gracefully", async () => {
    getLeaveLedger.mockRejectedValueOnce(new Error("Network Error"));

    const { result } = renderHook(() => useLeaveLedger());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.loadError).toBe(true);
    expect(result.current.entries).toEqual([]);
    expect(result.current.totalEntries).toBe(0);
  });

  it("refetches automatically when userId, page, or pageSize parameters change", async () => {
    getLeaveLedger.mockResolvedValue({
      data: { entries: [], totalEntries: 0 },
    });

    const { rerender } = renderHook((props) => useLeaveLedger(props), {
      initialProps: { userId: 42, page: 1, pageSize: 20 },
    });

    await waitFor(() => {
      expect(getLeaveLedger).toHaveBeenCalledWith({
        userId: 42,
        page: 1,
        pageSize: 20,
      });
    });

    rerender({ userId: 42, page: 2, pageSize: 20 });

    await waitFor(() => {
      expect(getLeaveLedger).toHaveBeenCalledWith({
        userId: 42,
        page: 2,
        pageSize: 20,
      });
    });
  });

  it("allows manual reloads via the returned load function", async () => {
    getLeaveLedger.mockResolvedValue({
      data: {
        entries: [{ entryId: 10, hours: "8.00" }],
        totalEntries: 1,
      },
    });

    const { result } = renderHook(() => useLeaveLedger({ userId: 101 }));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(getLeaveLedger).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.load();
    });

    expect(getLeaveLedger).toHaveBeenCalledTimes(2);
  });
});
