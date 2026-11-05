import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import {
  isWithdrawable,
  useMyLeaveRequests,
} from "@/pages/Leave/hooks/useMyLeaveRequests";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

const row = (overrides = {}) => ({
  requestId: 1,
  type: "paid",
  status: "pending",
  startDate: "2026-08-25",
  endDate: "2026-08-27",
  startTime: null,
  endTime: null,
  hours: "24.00",
  isLateNotice: false,
  requiredNoticeWorkdays: 6,
  reason: "Family trip",
  ...overrides,
});

const envelope = (data) => ({ success: true, message: "ok", data });

/** A refusal as axios delivers it: the server's wording is on the response. */
const refusal = (message) => {
  const error = new Error("Request failed");
  error.response = { data: { success: false, message } };
  return error;
};

describe("useMyLeaveRequests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMyLeaveRequests.mockResolvedValue(envelope([row()]));
  });

  it("shows a refusal in the server's own words", async () => {
    // Each refusal names the fix -- which request it clashed with, how much
    // notice was needed. A generic message would throw that away.
    api.submitLeaveRequest.mockRejectedValue(
      refusal("This overlaps request 501 (Aug 13 - Aug 15)."),
    );

    const { result } = renderHook(() => useMyLeaveRequests());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const saved = await result.current.file({ type: "paid" });

    expect(saved).toBe(false);
    await waitFor(() =>
      expect(result.current.saveError).toBe(
        "This overlaps request 501 (Aug 13 - Aug 15).",
      ),
    );
  });

  it("re-reads the list after filing so the hours appear", async () => {
    // The stored request carries figures the client never computed: the hours
    // the days came to, and whether it was marked short notice.
    api.submitLeaveRequest.mockResolvedValue(envelope(row()));

    const { result } = renderHook(() => useMyLeaveRequests());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const saved = await result.current.file({ type: "paid" });

    expect(saved).toBe(true);
    expect(api.getMyLeaveRequests).toHaveBeenCalledTimes(2);
  });

  it("ignores a second submission while one is in flight", async () => {
    let release;
    api.submitLeaveRequest.mockReturnValue(
      new Promise((resolve) => {
        release = resolve;
      }),
    );

    const { result } = renderHook(() => useMyLeaveRequests());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    const first = result.current.file({ type: "paid" });
    await waitFor(() => expect(result.current.isSaving).toBe(true));
    await result.current.file({ type: "paid" });

    expect(api.submitLeaveRequest).toHaveBeenCalledTimes(1);
    release(envelope(row()));
    await first;
  });

  it("re-reads the list after withdrawing", async () => {
    api.withdrawLeaveRequest.mockResolvedValue(envelope(row()));

    const { result } = renderHook(() => useMyLeaveRequests());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await result.current.withdraw(1);

    expect(api.withdrawLeaveRequest).toHaveBeenCalledWith(1);
    expect(api.getMyLeaveRequests).toHaveBeenCalledTimes(2);
  });

  it("asks nothing while the feature is switched off", () => {
    renderHook(() => useMyLeaveRequests({ enabled: false }));

    expect(api.getMyLeaveRequests).not.toHaveBeenCalled();
  });
});

describe("isWithdrawable", () => {
  it("is true only while a request is waiting", () => {
    // Approval is the end of the line: putting the hours back afterwards is an
    // admin adjustment with a note on it, not a button on this list.
    expect(isWithdrawable(row({ status: "pending" }))).toBe(true);
    expect(isWithdrawable(row({ status: "approved" }))).toBe(false);
    expect(isWithdrawable(row({ status: "rejected" }))).toBe(false);
    expect(isWithdrawable(row({ status: "withdrawn" }))).toBe(false);
  });
});
