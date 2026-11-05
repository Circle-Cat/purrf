import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { useLeaveBalances } from "@/pages/Leave/hooks/useLeaveBalances";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

const envelope = (data) => ({ success: true, message: "ok", data });

const overview = () => ({
  people: [
    {
      userId: 10,
      ldap: "ann",
      name: "Ann Employee",
      level: "L3",
      annualHours: 80,
      balanceHours: "72.00",
    },
  ],
  excluded: {
    left: [],
    noHireDate: [],
    unreadable: [],
    unresolved: [],
    notInternal: [],
  },
  profileCount: 1,
});

const written = () => ({
  userId: 10,
  hours: "-8.00",
  effectiveDate: "2026-08-20",
  note: "Leave taken in March",
  balanceHours: "64.00",
});

describe("useLeaveBalances", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getLeaveBalances.mockResolvedValue(envelope(overview()));
  });

  it("ignores a second correction while one is in flight", async () => {
    // The guard matters more here than anywhere else in the feature: nothing
    // on the server dedupes corrections, so a double click writes two ledger
    // rows and neither can be taken back.
    let release;
    api.adjustLeaveBalance.mockReturnValue(
      new Promise((resolve) => {
        release = resolve;
      }),
    );

    const { result } = renderHook(() => useLeaveBalances());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const first = result.current.adjust({ userId: 10, hours: "-8.00" });
    await waitFor(() => expect(result.current.isSaving).toBe(true));
    const second = await result.current.adjust({ userId: 10, hours: "-8.00" });

    expect(second).toBe(false);
    expect(api.adjustLeaveBalance).toHaveBeenCalledTimes(1);

    release(envelope(written()));
    await first;
  });

  it("keeps the balance the server returned", async () => {
    api.adjustLeaveBalance.mockResolvedValue(envelope(written()));

    const { result } = renderHook(() => useLeaveBalances());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await result.current.adjust({ userId: 10, hours: "-8.00" });

    await waitFor(() =>
      expect(result.current.lastResult?.balanceHours).toBe("64.00"),
    );
  });

  it("re-reads the overview after writing", async () => {
    api.adjustLeaveBalance.mockResolvedValue(envelope(written()));

    const { result } = renderHook(() => useLeaveBalances());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await result.current.adjust({ userId: 10, hours: "-8.00" });

    expect(api.getLeaveBalances).toHaveBeenCalledTimes(2);
  });

  it("keeps no stale result behind a refusal", async () => {
    api.adjustLeaveBalance.mockRejectedValue(
      Object.assign(new Error("Request failed"), {
        response: { data: { message: "A leave adjustment needs a note." } },
      }),
    );

    const { result } = renderHook(() => useLeaveBalances());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await result.current.adjust({ userId: 10, hours: "0" });

    await waitFor(() =>
      expect(result.current.saveError).toBe("A leave adjustment needs a note."),
    );
    expect(result.current.lastResult).toBeNull();
  });

  it("asks nothing while the feature is switched off", () => {
    renderHook(() => useLeaveBalances({ enabled: false }));

    expect(api.getLeaveBalances).not.toHaveBeenCalled();
  });
});
