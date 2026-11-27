import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

import {
  PREVIEW_DELAY_MS,
  useLeaveRequestPreview,
} from "@/pages/Leave/hooks/useLeaveRequestPreview";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

const payload = (overrides = {}) => ({
  type: "paid",
  startDate: "2026-12-22",
  endDate: "2026-12-29",
  startTime: null,
  endTime: null,
  ...overrides,
});

const answer = (data) => ({ success: true, message: "ok", data });

describe("useLeaveRequestPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("asks nothing while the form cannot be sent", async () => {
    const { result } = renderHook(() => useLeaveRequestPreview(null));

    await act(async () => {
      vi.advanceTimersByTime(PREVIEW_DELAY_MS * 2);
    });

    expect(api.previewLeaveRequest).not.toHaveBeenCalled();
    expect(result.current.preview).toBeNull();
    expect(result.current.previewError).toBeNull();
  });

  it("waits for typing to pause, then shows what the server worked out", async () => {
    api.previewLeaveRequest.mockResolvedValue(
      answer({ hours: "40.00", workdays: 5, daysNotCounted: [] }),
    );

    const { result } = renderHook(() => useLeaveRequestPreview(payload()));

    expect(api.previewLeaveRequest).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(PREVIEW_DELAY_MS);
    });

    expect(api.previewLeaveRequest).toHaveBeenCalledWith(payload());
    expect(result.current.preview).toEqual({
      hours: "40.00",
      workdays: 5,
      daysNotCounted: [],
    });
  });

  it("shows the server's reason when the dates cannot be filed", async () => {
    api.previewLeaveRequest.mockRejectedValue({
      response: { data: { message: "Those days are already time off." } },
    });

    const { result } = renderHook(() => useLeaveRequestPreview(payload()));
    await act(async () => {
      vi.advanceTimersByTime(PREVIEW_DELAY_MS);
    });

    expect(result.current.preview).toBeNull();
    expect(result.current.previewError).toBe(
      "Those days are already time off.",
    );
  });

  it("never shows an answer against dates it was not asked for", async () => {
    // A slow reply for the old dates must not land on the new ones.
    let resolveOld;
    api.previewLeaveRequest.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveOld = resolve;
      }),
    );
    api.previewLeaveRequest.mockResolvedValueOnce(
      answer({ hours: "8.00", workdays: 1, daysNotCounted: [] }),
    );

    const { result, rerender } = renderHook(
      ({ value }) => useLeaveRequestPreview(value),
      { initialProps: { value: payload() } },
    );
    await act(async () => {
      vi.advanceTimersByTime(PREVIEW_DELAY_MS);
    });
    rerender({
      value: payload({ startDate: "2026-12-22", endDate: "2026-12-22" }),
    });
    expect(result.current.preview).toBeNull();

    await act(async () => {
      resolveOld(answer({ hours: "40.00", workdays: 5, daysNotCounted: [] }));
    });
    expect(result.current.preview).toBeNull();

    await act(async () => {
      vi.advanceTimersByTime(PREVIEW_DELAY_MS);
    });
    expect(result.current.preview.hours).toBe("8.00");
  });
});
