import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import MeetingRescheduleDialog from "@/pages/PersonalDashboard/components/MeetingRescheduleDialog";

const meeting = {
  meetingId: "google-event-1",
  startDatetime: "2026-06-01T13:00:00Z",
  endDatetime: "2026-06-01T14:00:00Z",
};

/** Render with the dialog already open, in a fixed zone. */
function renderOpen(props = {}) {
  return render(
    <MeetingRescheduleDialog
      open
      onOpenChange={vi.fn()}
      meeting={meeting}
      userTimezone="UTC"
      onSubmit={vi.fn()}
      {...props}
    />,
  );
}

describe("MeetingRescheduleDialog", () => {
  // The dialog bounds its date input to "today" in the selected timezone,
  // so a fixed system time keeps that bound behind the fixture's fixed
  // 2026-06 dates instead of drifting past them as real time moves on.
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-05-01T00:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("prefills the meeting's current slot in the viewer's timezone", () => {
    renderOpen();
    expect(screen.getByLabelText("Date")).toHaveValue("2026-06-01");
    expect(screen.getByLabelText("Start time")).toHaveValue("13:00");
    // 13:00 -> 14:00 is one hour, which is an offered option.
    expect(screen.getByLabelText("Duration")).toHaveValue("60");
  });

  it("submits wall-clock values with no UTC conversion", () => {
    const onSubmit = vi.fn();
    renderOpen({ onSubmit });

    fireEvent.change(screen.getByLabelText("Date"), {
      target: { value: "2026-06-08" },
    });
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "09:30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSubmit).toHaveBeenCalledWith({
      date: "2026-06-08",
      startTime: "09:30",
      durationMinutes: 60,
      timezone: "UTC",
    });
  });

  it("falls back to the default duration for a slot length not offered", () => {
    renderOpen({
      meeting: {
        ...meeting,
        endDatetime: "2026-06-01T13:25:00Z", // 25 minutes
      },
    });
    expect(screen.getByLabelText("Duration")).toHaveValue("45");
  });

  it("does not submit while a date or time is missing", () => {
    const onSubmit = vi.fn();
    renderOpen({ onSubmit, meeting: { ...meeting, startDatetime: null } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
