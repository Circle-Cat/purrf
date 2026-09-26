import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { useMyLeaveLedger } from "@/pages/Leave/hooks/useMyLeaveLedger";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

const ledgerData = (overrides = {}) => ({
  totalHours: "120.00",
  entries: [
    {
      entryId: 1,
      type: "accrual",
      hours: "40.00",
      effectiveDate: "2026-01-01",
      note: "Annual accrual",
    },
    {
      entryId: 2,
      type: "deduction",
      hours: "8.00",
      effectiveDate: "2026-08-15",
      note: "Paid leave",
    },
  ],
  ...overrides,
});

const envelope = (data) => ({ success: true, message: "ok", data });

const refusal = (message) => {
  const error = new Error("Request failed");
  error.response = { data: { success: false, message } };
  return error;
};

describe("useMyLeaveLedger", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMyLeaveLedger.mockResolvedValue(envelope(ledgerData()));
  });

  it("loads ledger data on mount when enabled", async () => {
    const { result } = renderHook(() => useMyLeaveLedger());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.loadError).toBe(false);

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.data).toEqual(ledgerData());
    expect(result.current.loadError).toBe(false);
    expect(api.getMyLeaveLedger).toHaveBeenCalledTimes(1);
  });

  it("asks nothing while the feature is switched off", () => {
    renderHook(() => useMyLeaveLedger({ enabled: false }));

    expect(api.getMyLeaveLedger).not.toHaveBeenCalled();
  });

  it("surfaces a load error without throwing", async () => {
    api.getMyLeaveLedger.mockRejectedValue(refusal("Ledger not found"));

    const { result } = renderHook(() => useMyLeaveLedger());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.loadError).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it("re-reads the ledger when load is called manually", async () => {
    const { result } = renderHook(() => useMyLeaveLedger());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    api.getMyLeaveLedger.mockResolvedValueOnce(
      envelope(ledgerData({ totalHours: "200.00" })),
    );

    await result.current.load();

    await waitFor(() => expect(result.current.data.totalHours).toBe("200.00"));
    expect(api.getMyLeaveLedger).toHaveBeenCalledTimes(2);
  });

  it("clears loadError on a successful retry", async () => {
    api.getMyLeaveLedger.mockRejectedValueOnce(refusal("Server error"));

    const { result } = renderHook(() => useMyLeaveLedger());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.loadError).toBe(true);

    api.getMyLeaveLedger.mockResolvedValueOnce(envelope(ledgerData()));
    await result.current.load();

    await waitFor(() => expect(result.current.loadError).toBe(false));
    expect(result.current.data).toEqual(ledgerData());
  });

  it("does not fetch when enabled toggles to false mid-session", async () => {
    const { result, rerender } = renderHook(
      ({ enabled }) => useMyLeaveLedger({ enabled }),
      { initialProps: { enabled: true } },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(api.getMyLeaveLedger).toHaveBeenCalledTimes(1);

    rerender({ enabled: false });

    expect(api.getMyLeaveLedger).toHaveBeenCalledTimes(1);
  });
});
