import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
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
});
