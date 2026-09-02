import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import MeetingOverviewCard from "@/pages/PersonalDashboard/components/MeetingOverviewCard";

const mockOverview = {
  requiredMeetings: 3,
  completedCount: 2,
  completedRate: 67,
  meetingTimeList: [
    {
      meetingId: "m1",
      startDatetime: "2026-03-18T02:00:00Z",
      endDatetime: "2026-03-18T03:00:00Z",
      isCompleted: true,
    },
    {
      meetingId: "m2",
      startDatetime: "2026-04-01T05:00:00Z",
      endDatetime: "2026-04-01T06:00:00Z",
      isCompleted: true,
    },
  ],
};

describe("MeetingOverviewCard", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-01T00:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should display meeting statistics", () => {
    render(<MeetingOverviewCard overview={mockOverview} />);
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("67%")).toBeInTheDocument();
  });

  it("should show 'No meetings scheduled' when meetingTimeList is empty", () => {
    render(
      <MeetingOverviewCard
        overview={{ ...mockOverview, meetingTimeList: [] }}
      />,
    );
    expect(screen.getByText("No meetings scheduled.")).toBeInTheDocument();
  });

  it("should display the user timezone IANA next to each meeting", () => {
    render(
      <MeetingOverviewCard
        overview={mockOverview}
        userTimezone="Asia/Shanghai"
      />,
    );
    const timezoneLabels = screen.getAllByText(/Asia\/Shanghai/);
    expect(timezoneLabels.length).toBeGreaterThanOrEqual(2);
  });

  it("should show a DONE badge for each completed meeting", () => {
    render(<MeetingOverviewCard overview={mockOverview} />);
    const doneBadges = screen.getAllByText("DONE");
    expect(doneBadges).toHaveLength(mockOverview.meetingTimeList.length);
  });

  it("should render all meetings in the list", () => {
    render(<MeetingOverviewCard overview={mockOverview} />);
    const badges = screen.getAllByText("DONE");
    expect(badges).toHaveLength(mockOverview.meetingTimeList.length);
  });

  it("should show a SCHEDULED badge for a not-yet-completed meeting whose start time is in the future", () => {
    render(
      <MeetingOverviewCard
        overview={{
          ...mockOverview,
          meetingTimeList: [
            {
              meetingId: "m-future",
              startDatetime: "2026-03-02T23:30:00Z",
              endDatetime: "2026-03-03T00:30:00Z",
              isCompleted: false,
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("SCHEDULED")).toBeInTheDocument();
  });

  it("should show an INCOMPLETE badge for a not-yet-completed meeting whose start time has passed", () => {
    render(
      <MeetingOverviewCard
        overview={{
          ...mockOverview,
          meetingTimeList: [
            {
              meetingId: "m-past",
              startDatetime: "2026-02-28T23:30:00Z",
              endDatetime: "2026-03-01T00:30:00Z",
              isCompleted: false,
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("INCOMPLETE")).toBeInTheDocument();
    expect(screen.queryByText("SCHEDULED")).not.toBeInTheDocument();
  });

  it("should render a Join link pointing at the meet link for a scheduled meeting", () => {
    render(
      <MeetingOverviewCard
        overview={{
          ...mockOverview,
          meetingTimeList: [
            {
              meetingId: "m-google",
              startDatetime: "2026-03-02T23:30:00Z",
              endDatetime: "2026-03-03T00:30:00Z",
              isCompleted: false,
              meetLink: "https://meet.google.com/abc-defg-hij",
            },
          ],
        }}
      />,
    );
    const join = screen.getByRole("link", { name: /join/i });
    expect(join).toHaveAttribute(
      "href",
      "https://meet.google.com/abc-defg-hij",
    );
    expect(join).toHaveAttribute("target", "_blank");
    expect(join).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("should not render a Join link for a meeting that has no meet link", () => {
    render(
      <MeetingOverviewCard
        overview={{
          ...mockOverview,
          meetingTimeList: [
            {
              meetingId: "m-manual",
              startDatetime: "2026-03-02T23:30:00Z",
              endDatetime: "2026-03-03T00:30:00Z",
              isCompleted: false,
            },
          ],
        }}
      />,
    );
    expect(
      screen.queryByRole("link", { name: /join/i }),
    ).not.toBeInTheDocument();
  });

  it("should not render a Join link for a completed meeting", () => {
    render(
      <MeetingOverviewCard
        overview={{
          ...mockOverview,
          meetingTimeList: [
            {
              meetingId: "m-done",
              startDatetime: "2026-02-20T23:30:00Z",
              endDatetime: "2026-02-21T00:30:00Z",
              isCompleted: true,
              meetLink: "https://meet.google.com/abc-defg-hij",
            },
          ],
        }}
      />,
    );
    expect(
      screen.queryByRole("link", { name: /join/i }),
    ).not.toBeInTheDocument();
  });

  it("should still render a Join link for a meeting that has started but is not marked completed", () => {
    // A meeting whose start time has passed is INCOMPLETE, not COMPLETED --
    // and that is exactly the moment someone running late needs the link.
    render(
      <MeetingOverviewCard
        overview={{
          ...mockOverview,
          meetingTimeList: [
            {
              meetingId: "m-running-late",
              startDatetime: "2026-02-28T23:30:00Z",
              endDatetime: "2026-03-01T00:30:00Z",
              isCompleted: false,
              meetLink: "https://meet.google.com/abc-defg-hij",
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("INCOMPLETE")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /join/i })).toBeInTheDocument();
  });

  it("should still render a Join link shortly after a meeting ended without being marked completed", () => {
    // Ended 30 minutes before the mocked now -- inside the grace window.
    render(
      <MeetingOverviewCard
        overview={{
          ...mockOverview,
          meetingTimeList: [
            {
              meetingId: "m-just-ended",
              startDatetime: "2026-02-28T22:30:00Z",
              endDatetime: "2026-02-28T23:30:00Z",
              isCompleted: false,
              meetLink: "https://meet.google.com/abc-defg-hij",
            },
          ],
        }}
      />,
    );
    expect(screen.getByRole("link", { name: /join/i })).toBeInTheDocument();
  });

  it("should not render a Join link for a meeting that ended long ago and was never marked completed", () => {
    // A meeting nobody attended is never marked completed, so completion
    // alone would leave this button up forever.
    render(
      <MeetingOverviewCard
        overview={{
          ...mockOverview,
          meetingTimeList: [
            {
              meetingId: "m-no-show",
              startDatetime: "2026-02-20T23:30:00Z",
              endDatetime: "2026-02-21T00:30:00Z",
              isCompleted: false,
              meetLink: "https://meet.google.com/abc-defg-hij",
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("INCOMPLETE")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /join/i }),
    ).not.toBeInTheDocument();
  });

  describe("meeting ordering", () => {
    it("should list meetings newest start time first", () => {
      render(
        <MeetingOverviewCard
          overview={{
            ...mockOverview,
            meetingTimeList: [
              {
                meetingId: "march",
                startDatetime: "2026-03-18T02:00:00Z",
                endDatetime: "2026-03-18T03:00:00Z",
                isCompleted: false,
              },
              {
                meetingId: "may",
                startDatetime: "2026-05-18T02:00:00Z",
                endDatetime: "2026-05-18T03:00:00Z",
                isCompleted: false,
              },
              {
                meetingId: "april",
                startDatetime: "2026-04-18T02:00:00Z",
                endDatetime: "2026-04-18T03:00:00Z",
                isCompleted: false,
              },
            ],
          }}
          userTimezone="UTC"
        />,
      );

      const shown = screen
        .getAllByText(/^2026-0[345]-18$/)
        .map((node) => node.textContent);
      expect(shown).toEqual(["2026-05-18", "2026-04-18", "2026-03-18"]);
    });

    it("should leave a meeting with no usable start time at the end", () => {
      render(
        <MeetingOverviewCard
          overview={{
            ...mockOverview,
            meetingTimeList: [
              {
                meetingId: "broken",
                startDatetime: "not a date",
                endDatetime: "not a date",
                isCompleted: false,
              },
              {
                meetingId: "real",
                startDatetime: "2026-05-18T02:00:00Z",
                endDatetime: "2026-05-18T03:00:00Z",
                isCompleted: false,
              },
            ],
          }}
          userTimezone="UTC"
        />,
      );

      const rows = screen.getAllByText(/SCHEDULED|INCOMPLETE/);
      expect(rows).toHaveLength(2);
      expect(screen.getByText("2026-05-18")).toBeInTheDocument();
    });
  });

  describe("cancelling a meeting", () => {
    const mixedOverview = {
      ...mockOverview,
      meetingTimeList: [
        {
          meetingId: "m-scheduled",
          startDatetime: "2026-04-01T02:00:00Z",
          endDatetime: "2026-04-01T03:00:00Z",
          isCompleted: false,
        },
        {
          meetingId: "m-completed",
          startDatetime: "2026-02-10T02:00:00Z",
          endDatetime: "2026-02-10T03:00:00Z",
          isCompleted: true,
        },
        {
          meetingId: "m-past-incomplete",
          startDatetime: "2026-02-20T02:00:00Z",
          endDatetime: "2026-02-20T03:00:00Z",
          isCompleted: false,
        },
      ],
    };

    it("should offer a cancel control for the scheduled meeting only", () => {
      render(
        <MeetingOverviewCard
          overview={mixedOverview}
          userTimezone="UTC"
          canDelete
          onDeleteMeeting={vi.fn()}
        />,
      );

      // One control for m-scheduled; none for the completed or the past
      // uncompleted slot, which are history rather than something to call off.
      const controls = screen.getAllByRole("button", {
        name: /cancel meeting on/i,
      });
      expect(controls).toHaveLength(1);
      expect(controls[0]).toHaveAccessibleName(/2026-04-01/);
    });

    it("should not offer a cancel control when cancelling is not available to this viewer", () => {
      render(
        <MeetingOverviewCard overview={mixedOverview} userTimezone="UTC" />,
      );

      expect(
        screen.queryByRole("button", { name: /cancel meeting on/i }),
      ).not.toBeInTheDocument();
    });

    it("should hand the meeting over only after the confirmation is accepted", async () => {
      const onDeleteMeeting = vi.fn().mockResolvedValue(undefined);
      render(
        <MeetingOverviewCard
          overview={mixedOverview}
          userTimezone="UTC"
          canDelete
          onDeleteMeeting={onDeleteMeeting}
        />,
      );

      fireEvent.click(
        screen.getByRole("button", { name: /cancel meeting on/i }),
      );

      expect(screen.getByText("Cancel this meeting?")).toBeInTheDocument();
      expect(onDeleteMeeting).not.toHaveBeenCalled();

      await act(async () => {
        fireEvent.click(screen.getByRole("button", { name: "Cancel meeting" }));
      });

      expect(onDeleteMeeting).toHaveBeenCalledTimes(1);
      expect(onDeleteMeeting).toHaveBeenCalledWith(
        expect.objectContaining({ meetingId: "m-scheduled" }),
      );
    });

    it("should keep the meeting when the confirmation is declined", () => {
      const onDeleteMeeting = vi.fn();
      render(
        <MeetingOverviewCard
          overview={mixedOverview}
          userTimezone="UTC"
          canDelete
          onDeleteMeeting={onDeleteMeeting}
        />,
      );

      fireEvent.click(
        screen.getByRole("button", { name: /cancel meeting on/i }),
      );
      fireEvent.click(screen.getByRole("button", { name: "Keep it" }));

      expect(
        screen.queryByText("Cancel this meeting?"),
      ).not.toBeInTheDocument();
      expect(onDeleteMeeting).not.toHaveBeenCalled();
    });
  });
});
