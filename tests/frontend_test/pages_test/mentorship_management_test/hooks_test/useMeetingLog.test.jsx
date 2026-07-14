import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useMeetingLog } from "@/pages/MentorshipManagement/hooks/useMeetingLog";
import * as api from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi");

const log = (meetings, roundVersion = "v2") => ({
  data: { roundVersion, meetings },
});

describe("useMeetingLog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getMeetingLog.mockResolvedValue(log([]));
  });

  it("does not fetch while closed", () => {
    renderHook(() => useMeetingLog(80, false));
    expect(api.getMeetingLog).not.toHaveBeenCalled();
  });

  it("does not fetch when pairId is null even if open", () => {
    renderHook(() => useMeetingLog(null, true));
    expect(api.getMeetingLog).not.toHaveBeenCalled();
  });

  it("fetches once opened", async () => {
    renderHook(() => useMeetingLog(80, true));
    await waitFor(() => expect(api.getMeetingLog).toHaveBeenCalledWith(80));
    expect(api.getMeetingLog).toHaveBeenCalledTimes(1);
  });

  it("returns meetings and roundVersion on success", async () => {
    const meetings = [
      {
        meetingId: "gm-80-1",
        startDatetime: "2024-03-01T23:30:00Z",
        endDatetime: "2024-03-02T00:30:00Z",
        isCompleted: true,
        note: [],
        createDatetime: "2024-03-01T15:30:00Z",
      },
    ];
    api.getMeetingLog.mockResolvedValue(log(meetings, "v2"));

    const { result } = renderHook(() => useMeetingLog(80, true));

    await waitFor(() => expect(result.current.meetings).toEqual(meetings));
    expect(result.current.roundVersion).toBe("v2");
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(false);
  });

  it("sets error and stops loading on failure", async () => {
    api.getMeetingLog.mockRejectedValue(new Error("boom"));

    const { result } = renderHook(() => useMeetingLog(80, true));

    await waitFor(() => expect(result.current.error).toBe(true));
    expect(result.current.loading).toBe(false);
  });

  it("refetches every time it is closed and reopened", async () => {
    const { rerender } = renderHook(({ open }) => useMeetingLog(80, open), {
      initialProps: { open: true },
    });
    await waitFor(() => expect(api.getMeetingLog).toHaveBeenCalledTimes(1));

    rerender({ open: false });
    rerender({ open: true });

    await waitFor(() => expect(api.getMeetingLog).toHaveBeenCalledTimes(2));
  });

  it("ignores a stale response for a previous pairId", async () => {
    const resolvers = {};
    api.getMeetingLog.mockImplementation(
      (id) =>
        new Promise((resolve) => {
          resolvers[id] = resolve;
        }),
    );

    const { result, rerender } = renderHook(
      ({ pairId }) => useMeetingLog(pairId, true),
      { initialProps: { pairId: 1 } },
    );
    await waitFor(() => expect(resolvers[1]).toBeDefined());

    rerender({ pairId: 2 });
    await waitFor(() => expect(resolvers[2]).toBeDefined());

    // Newer pair (2) resolves first.
    await act(async () => {
      resolvers[2](
        log([
          {
            meetingId: "gm-2",
            startDatetime: "2024-04-01T23:30:00Z",
            endDatetime: "2024-04-02T00:30:00Z",
            isCompleted: true,
            note: [],
            createDatetime: "2024-04-01T15:30:00Z",
          },
        ]),
      );
    });
    // Stale pair (1) resolves last — must NOT overwrite pair 2's result.
    await act(async () => {
      resolvers[1](
        log([
          {
            meetingId: "gm-1",
            startDatetime: "2024-03-01T23:30:00Z",
            endDatetime: "2024-03-02T00:30:00Z",
            isCompleted: false,
            note: [],
            createDatetime: "2024-03-01T15:30:00Z",
          },
        ]),
      );
    });

    expect(result.current.meetings).toEqual([
      {
        meetingId: "gm-2",
        startDatetime: "2024-04-01T23:30:00Z",
        endDatetime: "2024-04-02T00:30:00Z",
        isCompleted: true,
        note: [],
        createDatetime: "2024-04-01T15:30:00Z",
      },
    ]);
  });
});
