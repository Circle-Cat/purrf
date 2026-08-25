import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";

import { useLeaveCalendarAdmin } from "@/pages/Leave/hooks/useLeaveCalendarAdmin";
import * as api from "@/api/leaveApi";

vi.mock("@/api/leaveApi");

const envelope = (data) => ({ success: true, message: "ok", data });

const segment = (overrides = {}) => ({
  name: "National Day",
  startDate: "2026-10-01",
  endDate: "2026-10-03",
  dayCount: 3,
  isExchangeable: true,
  ...overrides,
});

const refusal = (message) => {
  const error = new Error("Request failed");
  error.response = { data: { success: false, message } };
  return error;
};

describe("useLeaveCalendarAdmin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getLeaveHolidayYears.mockResolvedValue(
      envelope({ years: [2026], currentYear: 2026, nextYear: 2027 }),
    );
    api.getLeaveHolidays.mockResolvedValue(
      envelope({ year: 2026, totalDays: 3, segments: [segment()] }),
    );
    api.replaceLeaveHolidays.mockResolvedValue(
      envelope({ year: 2026, totalDays: 3, segments: [segment()] }),
    );
  });

  it("takes the current year from the server, not from the browser", async () => {
    // A browser in another timezone disagrees about the year, and on
    // 1 January that disagreement edits the wrong calendar.
    const { result } = renderHook(() => useLeaveCalendarAdmin());

    await waitFor(() => expect(result.current.year).toBe(2026));
    expect(api.getLeaveHolidays).toHaveBeenCalledWith(2026);
  });

  it("offers next year even before it holds anything", async () => {
    const { result } = renderHook(() => useLeaveCalendarAdmin());

    await waitFor(() => expect(result.current.years).toEqual([2026, 2027]));
  });

  it("is not dirty until something is edited", async () => {
    const { result } = renderHook(() => useLeaveCalendarAdmin());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.isDirty).toBe(false);

    act(() => result.current.edit(0, "name", "Spring Festival"));

    expect(result.current.isDirty).toBe(true);
    expect(result.current.segments[0].name).toBe("Spring Festival");
  });

  it("sends the whole year, including rows nobody touched", async () => {
    // The endpoint replaces the year. Sending only what changed would delete
    // everything else.
    api.getLeaveHolidays.mockResolvedValue(
      envelope({
        year: 2026,
        totalDays: 4,
        segments: [
          segment(),
          segment({
            name: "Labour Day",
            startDate: "2026-05-01",
            endDate: "2026-05-01",
          }),
        ],
      }),
    );

    const { result } = renderHook(() => useLeaveCalendarAdmin());
    await waitFor(() => expect(result.current.segments).toHaveLength(2));

    act(() => result.current.edit(0, "isExchangeable", false));
    await act(async () => {
      await result.current.save();
    });

    const sent = api.replaceLeaveHolidays.mock.calls[0];
    expect(sent[0]).toBe(2026);
    expect(sent[1]).toHaveLength(2);
    expect(sent[1][0]).toEqual({
      name: "National Day",
      startDate: "2026-10-01",
      endDate: "2026-10-03",
      isExchangeable: false,
    });
  });

  it("a removed row is simply absent, which is how it is deleted", async () => {
    const { result } = renderHook(() => useLeaveCalendarAdmin());
    await waitFor(() => expect(result.current.segments).toHaveLength(1));

    act(() => result.current.remove(0));
    await act(async () => {
      await result.current.save();
    });

    expect(api.replaceLeaveHolidays.mock.calls[0][1]).toEqual([]);
  });

  it("re-reads after saving rather than trusting the local rows", async () => {
    // The server derives segments back out of the days it stored, so two
    // adjacent runs sharing a name come back as one.
    const { result } = renderHook(() => useLeaveCalendarAdmin());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => result.current.add());
    await act(async () => {
      await result.current.save();
    });

    await waitFor(() => expect(api.getLeaveHolidays).toHaveBeenCalledTimes(2));
    expect(result.current.isDirty).toBe(false);
  });

  it("shows a refusal in the server's own words", async () => {
    // Each one names the holiday at fault, which a generic message loses.
    api.replaceLeaveHolidays.mockRejectedValue(
      refusal("National Day and Labour Day both cover 2026-10-01."),
    );

    const { result } = renderHook(() => useLeaveCalendarAdmin());
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    act(() => result.current.add());
    const saved = await result.current.save();

    expect(saved).toBe(false);
    await waitFor(() =>
      expect(result.current.saveError).toBe(
        "National Day and Labour Day both cover 2026-10-01.",
      ),
    );
  });

  it("asks nothing while the feature is switched off", () => {
    renderHook(() => useLeaveCalendarAdmin({ enabled: false }));

    expect(api.getLeaveHolidayYears).not.toHaveBeenCalled();
    expect(api.getLeaveHolidays).not.toHaveBeenCalled();
  });
});
