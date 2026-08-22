import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { useLeaveApprovals } from "@/pages/Leave/hooks/useLeaveApprovals";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

/** One row of the approvals response, as the server sends it (camelCase). */
const row = (overrides = {}) => ({
  requestId: 1,
  userId: 10,
  employeeName: "Ann Employee",
  employeeLdap: "aemployee",
  requiredNoticeWorkdays: 6,
  balanceBefore: "88.25",
  balanceAfter: "80.25",
  type: "paid",
  status: "pending",
  startDate: "2026-08-13",
  endDate: "2026-08-15",
  startTime: null,
  endTime: null,
  hours: "24.00",
  isOverdraft: false,
  isLateNotice: false,
  reason: "Holiday",
  approverUserId: 20,
  decidedBy: null,
  decidedAt: null,
  ...overrides,
});

/** The API envelope: `data` is the list itself, not a keyed object. */
const envelope = (rows) => ({ success: true, message: "ok", data: rows });

describe("useLeaveApprovals", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches nothing while the feature is switched off", () => {
    // A feature that is off must not be calling its endpoint on every
    // dashboard load.
    const { result } = renderHook(() => useLeaveApprovals({ enabled: false }));

    expect(api.getLeaveApprovals).not.toHaveBeenCalled();
    expect(result.current.isApprover).toBe(false);
  });

  it("does not claim the viewer is an approver while loading", () => {
    api.getLeaveApprovals.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useLeaveApprovals());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.isApprover).toBe(false);
  });

  it("does not claim the viewer is an approver after a failed load", async () => {
    // Fails closed: a broken fetch must not put up an entry point that leads
    // to a page we could not load either.
    api.getLeaveApprovals.mockRejectedValue(new Error("network error"));

    const { result } = renderHook(() => useLeaveApprovals());

    await waitFor(() => expect(result.current.loadError).toBe(true));
    expect(result.current.isApprover).toBe(false);
  });

  it("nobody has filed against you means you are not an approver", async () => {
    api.getLeaveApprovals.mockResolvedValue(envelope([]));

    const { result } = renderHook(() => useLeaveApprovals());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isApprover).toBe(false);
  });

  it("stays an approver once the queue is empty but history is not", async () => {
    // The rule the entry point rests on. A manager who has decided everything
    // has an empty queue, and hiding the entry then would take away the only
    // place that answers "did I approve that".
    api.getLeaveApprovals.mockResolvedValue(
      envelope([row({ status: "approved", decidedBy: 20 })]),
    );

    const { result } = renderHook(() => useLeaveApprovals());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isApprover).toBe(true);
    expect(result.current.pendingCount).toBe(0);
    expect(result.current.decided).toHaveLength(1);
  });

  it("counts only what is still waiting", async () => {
    api.getLeaveApprovals.mockResolvedValue(
      envelope([
        row({ requestId: 1, status: "pending" }),
        row({ requestId: 2, status: "approved" }),
        row({ requestId: 3, status: "rejected" }),
        row({ requestId: 4, status: "withdrawn" }),
        row({ requestId: 5, status: "pending" }),
      ]),
    );

    const { result } = renderHook(() => useLeaveApprovals());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.pendingCount).toBe(2);
    expect(result.current.pending.map((r) => r.requestId)).toEqual([1, 5]);
    expect(result.current.decided.map((r) => r.requestId)).toEqual([2, 3, 4]);
  });

  it("re-reads the list after a decision so the queue cannot go stale", async () => {
    api.getLeaveApprovals.mockResolvedValue(envelope([row()]));
    api.decideLeaveRequest.mockResolvedValue(
      envelope(row({ status: "approved" })),
    );

    const { result } = renderHook(() => useLeaveApprovals());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await result.current.decide(1, true);

    expect(api.decideLeaveRequest).toHaveBeenCalledWith(1, true);
    expect(api.getLeaveApprovals).toHaveBeenCalledTimes(2);
  });

  it("ignores a second decision while one is in flight", async () => {
    // Approving is irreversible. A double click would otherwise send a second
    // decision the server refuses, which reads as the first one having failed.
    api.getLeaveApprovals.mockResolvedValue(envelope([row()]));
    let release;
    api.decideLeaveRequest.mockReturnValue(
      new Promise((resolve) => {
        release = resolve;
      }),
    );

    const { result } = renderHook(() => useLeaveApprovals());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const first = result.current.decide(1, true);
    await waitFor(() => expect(result.current.decidingId).toBe(1));
    await result.current.decide(1, true);

    expect(api.decideLeaveRequest).toHaveBeenCalledTimes(1);

    release(envelope(row({ status: "approved" })));
    await first;
    await waitFor(() => expect(result.current.decidingId).toBe(null));
  });

  it("reports a failed decision and lets the next one through", async () => {
    api.getLeaveApprovals.mockResolvedValue(envelope([row()]));
    api.decideLeaveRequest.mockRejectedValue(new Error("network error"));

    const { result } = renderHook(() => useLeaveApprovals());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await result.current.decide(1, true);

    await waitFor(() => expect(result.current.decideError).toBe(true));
    expect(result.current.decidingId).toBe(null);
  });
});
